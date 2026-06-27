"""
WatermelonDB sync integration tests.

Four mandatory scenarios:
  1. Two devices pushing conflicting status changes → furthest-along wins.
  2. Stale client total → server always recomputes, client value ignored.
  3. Duplicate offline-generated pickup code → server reassigns to the second order.
  4. Out-of-order arrival → server_seq is assigned by arrival order, not device time.

Plus pull correctness, idempotency, customer sync, and payment append-only.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from app.models.branch import Branch
from app.models.customer import Customer
from app.models.order import Order, OrderStatus, Turnaround
from app.models.organization import Organization
from app.models.price_rule import PriceRule
from app.models.service import Service
from app.models.staff import Staff, StaffRole
from app.services.auth import create_access_token, hash_password
from app.services.sync import furthest_status, offline_pickup_code

# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
async def org(db_session):
    o = Organization(name="Sync Test Org")
    db_session.add(o)
    await db_session.flush()
    return o


@pytest.fixture
async def branch(db_session, org):
    b = Branch(name="Sync Branch", organization_id=org.id)
    db_session.add(b)
    await db_session.flush()
    return b


@pytest.fixture
async def attendant(db_session, branch):
    s = Staff(
        name="Sync Att", email="sync_att@test.com",
        role=StaffRole.attendant, branch_id=branch.id,
        password_hash=hash_password("pass"),
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
def token(attendant):
    return create_access_token(attendant.id, attendant.role.value, attendant.branch_id)


def auth(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture
async def wash_svc(db_session):
    s = Service(name="Sync Wash")
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def price_rule(db_session, wash_svc):
    r = PriceRule(service_id=wash_svc.id, tier=1, price_kobo=100_000)
    db_session.add(r)
    await db_session.flush()
    return r


@pytest.fixture
async def customer(db_session):
    c = Customer(name="Sync Customer", phone="08055501111", tier=1)
    db_session.add(c)
    await db_session.flush()
    return c


@pytest.fixture
async def server_order(db_session, branch, attendant, customer, price_rule, wash_svc):
    """A server-side order already in 'received' state."""
    from sqlalchemy import text
    seq = (await db_session.execute(text("SELECT nextval('sync_global_seq')"))).scalar()
    o = Order(
        branch_id=branch.id,
        attendant_id=attendant.id,
        customer_id=customer.id,
        status=OrderStatus.received,
        turnaround=Turnaround.regular,
        pickup_code="SRVORDER1",
        total_kobo=100_000,
        version=1,
        server_seq=seq,
    )
    db_session.add(o)
    await db_session.flush()
    return o


def _new_id() -> str:
    return str(uuid.uuid4())


def offline_order_payload(
    branch_id: str,
    attendant_id: str,
    customer_id: str,
    service_id: str,
    *,
    piece_count: int = 1,
    turnaround: str = "regular",
    pickup_code: str | None = None,
    total_kobo: int = 99999,  # wrong value — server must recompute
    order_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": order_id or _new_id(),
        "branch_id": branch_id,
        "attendant_id": attendant_id,
        "customer_id": customer_id,
        "turnaround": turnaround,
        "pickup_code": pickup_code or "OFFLINE01",
        "total_kobo": total_kobo,
        "lines": [{"service_id": service_id, "piece_count": piece_count}],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Pure-function unit tests
# ─────────────────────────────────────────────────────────────────────────────


class TestFurthestStatus:
    def test_higher_rank_wins(self):
        assert furthest_status(OrderStatus.received, OrderStatus.processing) == OrderStatus.processing

    def test_same_rank_keeps_first(self):
        assert furthest_status(OrderStatus.processing, OrderStatus.processing) == OrderStatus.processing

    def test_lower_rank_loses(self):
        assert furthest_status(OrderStatus.ready, OrderStatus.received) == OrderStatus.ready

    def test_ready_beats_processing(self):
        assert furthest_status(OrderStatus.processing, OrderStatus.ready) == OrderStatus.ready

    def test_picked_up_is_terminal(self):
        assert furthest_status(OrderStatus.picked_up, OrderStatus.received) == OrderStatus.picked_up


class TestOfflinePickupCode:
    def test_embeds_branch_prefix(self):
        code = offline_pickup_code("AABBCC-1234", "DEVICE-XXXX")
        assert code.startswith("AAB")

    def test_embeds_device_prefix(self):
        code = offline_pickup_code("BRANCH-XXXX", "DDEEEE-1234")
        assert code[3:6] == "DDE"

    def test_length_is_eleven(self):
        assert len(offline_pickup_code("b1b2b3-xxxx", "d1d2d3-xxxx")) == 11

    def test_different_branches_different_prefix(self):
        c1 = offline_pickup_code("AAAAAA-1111", "DDDDDD-0000")
        c2 = offline_pickup_code("BBBBBB-2222", "DDDDDD-0000")
        assert c1[:3] != c2[:3]

    def test_different_devices_different_prefix(self):
        c1 = offline_pickup_code("AAAAAA-1111", "DDDDDD-0000")
        c2 = offline_pickup_code("AAAAAA-1111", "EEEEEE-9999")
        assert c1[3:6] != c2[3:6]


# ─────────────────────────────────────────────────────────────────────────────
# Pull endpoint
# ─────────────────────────────────────────────────────────────────────────────


class TestPull:
    async def test_pull_returns_all_with_since_zero(
        self, client: AsyncClient, token, server_order
    ):
        resp = await client.get("/sync/pull?since=0", headers=auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "orders" in data["changes"]
        assert "payments" in data["changes"]
        assert "customers" in data["changes"]
        ids = {o["id"] for o in data["changes"]["orders"]}
        assert server_order.id in ids

    async def test_pull_since_filters_older_records(
        self, client: AsyncClient, token, server_order
    ):
        high_seq = server_order.server_seq + 1000
        resp = await client.get(f"/sync/pull?since={high_seq}", headers=auth(token))
        assert resp.status_code == 200
        ids = {o["id"] for o in resp.json()["changes"]["orders"]}
        assert server_order.id not in ids

    async def test_pull_response_includes_server_seq(
        self, client: AsyncClient, token, server_order
    ):
        resp = await client.get("/sync/pull?since=0", headers=auth(token))
        assert resp.json()["server_seq"] >= server_order.server_seq

    async def test_records_include_server_seq_field(
        self, client: AsyncClient, token, server_order
    ):
        resp = await client.get("/sync/pull?since=0", headers=auth(token))
        orders = resp.json()["changes"]["orders"]
        matching = [o for o in orders if o["id"] == server_order.id]
        assert matching and matching[0]["server_seq"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1: conflicting status changes from two devices
# ─────────────────────────────────────────────────────────────────────────────


class TestConflictingStatusChanges:
    async def test_furthest_along_status_wins(
        self, client: AsyncClient, token, db_session, server_order
    ):
        oid = server_order.id

        # Device B pushes status=ready (skipping processing — allowed in offline mode)
        await client.post("/sync/push", json={
            "device_id": "device-b",
            "changes": {"orders": {"updated": [{"id": oid, "status": "ready"}]}},
        }, headers=auth(token))

        # Device A pushes status=processing (stale, behind B)
        await client.post("/sync/push", json={
            "device_id": "device-a",
            "changes": {"orders": {"updated": [{"id": oid, "status": "processing"}]}},
        }, headers=auth(token))

        # Server should keep "ready" — the furthest-along
        await db_session.refresh(server_order)
        assert server_order.status == OrderStatus.ready

    async def test_backward_push_leaves_status_unchanged(
        self, client: AsyncClient, token, db_session, server_order
    ):
        oid = server_order.id

        # Advance to processing
        await client.post("/sync/push", json={
            "device_id": "device-a",
            "changes": {"orders": {"updated": [{"id": oid, "status": "processing"}]}},
        }, headers=auth(token))
        await db_session.refresh(server_order)
        assert server_order.status == OrderStatus.processing

        # Stale device tries to push received (backward)
        await client.post("/sync/push", json={
            "device_id": "device-b",
            "changes": {"orders": {"updated": [{"id": oid, "status": "received"}]}},
        }, headers=auth(token))

        await db_session.refresh(server_order)
        # Must stay at processing — backward move silently ignored
        assert server_order.status == OrderStatus.processing

    async def test_status_advance_bumps_version(
        self, client: AsyncClient, token, db_session, server_order
    ):
        v0 = server_order.version
        await client.post("/sync/push", json={
            "device_id": "device-a",
            "changes": {"orders": {"updated": [{"id": server_order.id, "status": "processing"}]}},
        }, headers=auth(token))
        await db_session.refresh(server_order)
        assert server_order.version == v0 + 1

    async def test_stale_status_does_not_bump_version(
        self, client: AsyncClient, token, db_session, server_order
    ):
        # Advance to ready
        await client.post("/sync/push", json={
            "device_id": "device-a",
            "changes": {"orders": {"updated": [{"id": server_order.id, "status": "ready"}]}},
        }, headers=auth(token))
        await db_session.refresh(server_order)
        v_after = server_order.version

        # Push received (stale) — version must not change
        await client.post("/sync/push", json={
            "device_id": "device-b",
            "changes": {"orders": {"updated": [{"id": server_order.id, "status": "received"}]}},
        }, headers=auth(token))
        await db_session.refresh(server_order)
        assert server_order.version == v_after


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2: stale client total — server always recomputes
# ─────────────────────────────────────────────────────────────────────────────


class TestStaleClientTotal:
    async def test_server_ignores_client_total_kobo(
        self, client: AsyncClient, token, db_session,
        branch, attendant, customer, price_rule, wash_svc
    ):
        order_id = _new_id()
        payload = offline_order_payload(
            branch.id, attendant.id, customer.id, wash_svc.id,
            piece_count=2,
            total_kobo=1,           # deliberately wrong
            pickup_code="STALE001",
            order_id=order_id,
        )

        resp = await client.post("/sync/push", json={
            "device_id": "device-a",
            "changes": {"orders": {"created": [payload]}},
        }, headers=auth(token))
        assert resp.status_code == 200

        from sqlalchemy import select
        from app.models.order import Order as OrderModel
        order = (await db_session.execute(
            select(OrderModel).where(OrderModel.id == order_id)
        )).scalar_one()

        # 2 × 100,000 kobo = 200,000 — not the client's 1
        assert order.total_kobo == 200_000

    async def test_express_total_computed_correctly(
        self, client: AsyncClient, token, db_session,
        branch, attendant, customer, price_rule, wash_svc
    ):
        """Server must apply the turnaround multiplier (1.5×) correctly."""
        order_id = _new_id()
        payload = offline_order_payload(
            branch.id, attendant.id, customer.id, wash_svc.id,
            piece_count=1,
            turnaround="express",
            total_kobo=0,            # wrong
            pickup_code="EXPRESS01",
            order_id=order_id,
        )
        await client.post("/sync/push", json={
            "device_id": "device-a",
            "changes": {"orders": {"created": [payload]}},
        }, headers=auth(token))

        from sqlalchemy import select
        from app.models.order import Order as OrderModel
        order = (await db_session.execute(
            select(OrderModel).where(OrderModel.id == order_id)
        )).scalar_one()
        # 1 × 100,000 × 1.5 = 150,000 (ceiling: (100000*3+1)//2 = 150000)
        assert order.total_kobo == 150_000


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 3: duplicate offline pickup code
# ─────────────────────────────────────────────────────────────────────────────


class TestDuplicatePickupCode:
    async def test_second_order_gets_new_code(
        self, client: AsyncClient, token, db_session,
        branch, attendant, customer, price_rule, wash_svc
    ):
        shared_code = "DUPCODE01"

        order_a_id = _new_id()
        await client.post("/sync/push", json={
            "device_id": "device-a",
            "changes": {"orders": {"created": [offline_order_payload(
                branch.id, attendant.id, customer.id, wash_svc.id,
                pickup_code=shared_code, order_id=order_a_id,
            )]}},
        }, headers=auth(token))

        order_b_id = _new_id()
        resp = await client.post("/sync/push", json={
            "device_id": "device-b",
            "changes": {"orders": {"created": [offline_order_payload(
                branch.id, attendant.id, customer.id, wash_svc.id,
                pickup_code=shared_code, order_id=order_b_id,
            )]}},
        }, headers=auth(token))

        data = resp.json()
        assert shared_code in data["reassigned_codes"]
        new_code = data["reassigned_codes"][shared_code]
        assert new_code != shared_code

        from sqlalchemy import select
        from app.models.order import Order as OrderModel
        order_a = (await db_session.execute(
            select(OrderModel).where(OrderModel.id == order_a_id)
        )).scalar_one()
        order_b = (await db_session.execute(
            select(OrderModel).where(OrderModel.id == order_b_id)
        )).scalar_one()

        assert order_a.pickup_code == shared_code
        assert order_b.pickup_code == new_code
        assert order_a.pickup_code != order_b.pickup_code

    async def test_no_reassignment_when_no_collision(
        self, client: AsyncClient, token,
        branch, attendant, customer, price_rule, wash_svc
    ):
        resp = await client.post("/sync/push", json={
            "device_id": "device-a",
            "changes": {"orders": {"created": [offline_order_payload(
                branch.id, attendant.id, customer.id, wash_svc.id,
                pickup_code="UNIQUE001",
            )]}},
        }, headers=auth(token))
        assert resp.json()["reassigned_codes"] == {}

    async def test_idempotent_push_no_duplicate(
        self, client: AsyncClient, token, db_session,
        branch, attendant, customer, price_rule, wash_svc
    ):
        """Pushing the same order twice must not create two rows."""
        order_id = _new_id()
        payload = offline_order_payload(
            branch.id, attendant.id, customer.id, wash_svc.id,
            pickup_code="IDEMP001", order_id=order_id,
        )
        for _ in range(2):
            await client.post("/sync/push", json={
                "device_id": "device-a",
                "changes": {"orders": {"created": [payload]}},
            }, headers=auth(token))

        from sqlalchemy import select, func
        from app.models.order import Order as OrderModel
        count = (await db_session.execute(
            select(func.count()).where(OrderModel.id == order_id)
        )).scalar()
        assert count == 1


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 4: out-of-order arrival
# ─────────────────────────────────────────────────────────────────────────────


class TestOutOfOrderArrival:
    async def test_server_seq_assigned_by_arrival_not_creation_time(
        self, client: AsyncClient, token, db_session,
        branch, attendant, customer, price_rule, wash_svc, server_order
    ):
        """
        Device B's payment was 'created later' on-device, but its push arrives
        at the server before device A's push.  The server assigns server_seq in
        arrival order — B gets a lower seq than A.
        """
        oid = server_order.id

        pay_b_id = _new_id()  # "created later" on device B
        pay_a_id = _new_id()  # "created earlier" on device A

        # B arrives first
        await client.post("/sync/push", json={
            "device_id": "device-b",
            "changes": {"payments": {"created": [{
                "id": pay_b_id, "order_id": oid,
                "amount_kobo": 30_000, "method": "pos",
            }]}},
        }, headers=auth(token))

        # A arrives second (out-of-order relative to device creation time)
        await client.post("/sync/push", json={
            "device_id": "device-a",
            "changes": {"payments": {"created": [{
                "id": pay_a_id, "order_id": oid,
                "amount_kobo": 20_000, "method": "cash",
            }]}},
        }, headers=auth(token))

        from sqlalchemy import select
        from app.models.payment import Payment as PaymentModel
        pay_b = (await db_session.execute(
            select(PaymentModel).where(PaymentModel.id == pay_b_id)
        )).scalar_one()
        pay_a = (await db_session.execute(
            select(PaymentModel).where(PaymentModel.id == pay_a_id)
        )).scalar_one()

        # B arrived first → lower server_seq
        assert pay_b.server_seq < pay_a.server_seq

    async def test_pull_returns_both_payments_after_out_of_order_push(
        self, client: AsyncClient, token, db_session,
        branch, attendant, customer, price_rule, wash_svc, server_order
    ):
        oid = server_order.id
        seq_before = server_order.server_seq

        pay_b_id = _new_id()
        pay_a_id = _new_id()

        await client.post("/sync/push", json={
            "device_id": "device-b",
            "changes": {"payments": {"created": [{
                "id": pay_b_id, "order_id": oid,
                "amount_kobo": 30_000, "method": "pos",
            }]}},
        }, headers=auth(token))

        await client.post("/sync/push", json={
            "device_id": "device-a",
            "changes": {"payments": {"created": [{
                "id": pay_a_id, "order_id": oid,
                "amount_kobo": 20_000, "method": "cash",
            }]}},
        }, headers=auth(token))

        resp = await client.get(f"/sync/pull?since={seq_before}", headers=auth(token))
        payment_ids = {p["id"] for p in resp.json()["changes"]["payments"]}
        assert pay_a_id in payment_ids
        assert pay_b_id in payment_ids


# ─────────────────────────────────────────────────────────────────────────────
# Payment append-only via sync
# ─────────────────────────────────────────────────────────────────────────────


class TestSyncPayments:
    async def test_payment_push_is_idempotent(
        self, client: AsyncClient, token, db_session,
        branch, attendant, customer, price_rule, wash_svc, server_order
    ):
        oid = server_order.id
        pay_id = _new_id()
        payload = {
            "device_id": "device-a",
            "changes": {"payments": {"created": [{
                "id": pay_id, "order_id": oid,
                "amount_kobo": 50_000, "method": "cash",
            }]}},
        }
        for _ in range(3):
            await client.post("/sync/push", json=payload, headers=auth(token))

        from sqlalchemy import select, func
        from app.models.payment import Payment as PaymentModel
        count = (await db_session.execute(
            select(func.count()).where(PaymentModel.id == pay_id)
        )).scalar()
        assert count == 1


# ─────────────────────────────────────────────────────────────────────────────
# Customer sync
# ─────────────────────────────────────────────────────────────────────────────


class TestSyncCustomers:
    async def test_customer_created_offline_is_synced(
        self, client: AsyncClient, token, db_session
    ):
        cust_id = _new_id()
        await client.post("/sync/push", json={
            "device_id": "device-a",
            "changes": {"customers": {"created": [{
                "id": cust_id, "name": "Offline Cust",
                "phone": "08099990001", "tier": 1,
            }]}},
        }, headers=auth(token))

        from sqlalchemy import select
        from app.models.customer import Customer as CustomerModel
        c = (await db_session.execute(
            select(CustomerModel).where(CustomerModel.id == cust_id)
        )).scalar_one()
        assert c.name == "Offline Cust"
        assert c.server_seq is not None

    async def test_customer_appears_in_next_pull(
        self, client: AsyncClient, token
    ):
        cust_id = _new_id()
        push_resp = await client.post("/sync/push", json={
            "device_id": "device-a",
            "changes": {"customers": {"created": [{
                "id": cust_id, "name": "Pull Cust",
                "phone": "08099990002", "tier": 2,
            }]}},
        }, headers=auth(token))
        seq_after = push_resp.json()["server_seq"]

        pull_resp = await client.get(f"/sync/pull?since={seq_after - 1}", headers=auth(token))
        ids = {c["id"] for c in pull_resp.json()["changes"]["customers"]}
        assert cust_id in ids
