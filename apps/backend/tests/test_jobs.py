"""
Tests for the notification job layer.

Three layers tested independently:
  1. Enqueuing — endpoint calls enqueue the right job with right event
  2. Receipt builder — pure function, no DB
  3. Job execution — send_receipt() called directly with fake provider + test session
"""

import pytest

from app.jobs.receipts import Receipt, ReceiptLine, build_receipt_text, send_receipt
from app.models.branch import Branch
from app.models.customer import Customer
from app.models.order import Order, Turnaround
from app.models.order_line import OrderLine
from app.models.organization import Organization
from app.models.payment import Payment, PaymentMethod
from app.models.price_rule import PriceRule
from app.models.service import Service
from app.models.staff import Staff, StaffRole
from app.notifications.fake import FakeNotificationProvider
from app.queue import MemoryTaskQueue
from app.services.auth import create_access_token, hash_password


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def org(db_session):
    o = Organization(name="Job Test Org")
    db_session.add(o)
    await db_session.flush()
    return o


@pytest.fixture
async def branch(db_session, org):
    b = Branch(name="Job Branch", organization_id=org.id)
    db_session.add(b)
    await db_session.flush()
    return b


@pytest.fixture
async def attendant(db_session, branch):
    s = Staff(
        name="Job Attendant", email="job_att@test.com",
        role=StaffRole.attendant, branch_id=branch.id,
        password_hash=hash_password("pass"),
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
def token(attendant):
    return create_access_token(attendant.id, attendant.role.value, attendant.branch_id)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def wash_svc(db_session):
    s = Service(name="Wash & Fold")
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def iron_svc(db_session):
    s = Service(name="Ironing")
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def rules(db_session, wash_svc, iron_svc):
    rows = [
        PriceRule(service_id=wash_svc.id, tier=1, price_kobo=100_000),
        PriceRule(service_id=iron_svc.id, tier=1, price_kobo=50_000),
    ]
    for r in rows:
        db_session.add(r)
    await db_session.flush()
    return rows


@pytest.fixture
async def customer(db_session):
    c = Customer(name="Adaeze Obi", phone="08012345678", tier=1)
    db_session.add(c)
    await db_session.flush()
    return c


@pytest.fixture
async def order_via_api(client, branch, token, customer, rules, wash_svc, iron_svc):
    """Place a 2-line order via the API: wash×2 + iron×1 @ tier-1 regular."""
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": customer.id,
            "turnaround": "regular",
            "lines": [
                {"service_id": wash_svc.id, "piece_count": 2},
                {"service_id": iron_svc.id, "piece_count": 1},
            ],
        },
        headers=auth(token),
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# 1. Enqueuing — verify jobs land in the queue
# ---------------------------------------------------------------------------


class TestEnqueuing:
    async def test_payment_enqueues_paid_receipt_job(self, client, fake_queue, token, order_via_api):
        oid = order_via_api["id"]
        await client.post(
            f"/orders/{oid}/payments",
            json={"amount_kobo": 50_000, "method": "cash"},
            headers=auth(token),
        )
        paid_jobs = [j for j in fake_queue.jobs if j["name"] == "send_receipt" and j["kwargs"]["event"] == "paid"]
        assert len(paid_jobs) == 1
        assert paid_jobs[0]["kwargs"]["order_id"] == oid

    async def test_each_payment_enqueues_a_job(self, client, fake_queue, token, order_via_api):
        oid = order_via_api["id"]
        fake_queue.clear()
        await client.post(f"/orders/{oid}/payments", json={"amount_kobo": 10_000, "method": "cash"}, headers=auth(token))
        await client.post(f"/orders/{oid}/payments", json={"amount_kobo": 20_000, "method": "pos"}, headers=auth(token))
        paid_jobs = [j for j in fake_queue.jobs if j["kwargs"]["event"] == "paid"]
        assert len(paid_jobs) == 2

    async def test_ready_status_enqueues_ready_receipt_job(self, client, fake_queue, token, order_via_api):
        oid = order_via_api["id"]
        fake_queue.clear()
        await client.post(f"/orders/{oid}/status", json={"to_status": "processing"}, headers=auth(token))
        assert not any(j["kwargs"].get("event") == "ready" for j in fake_queue.jobs)
        await client.post(f"/orders/{oid}/status", json={"to_status": "ready"}, headers=auth(token))
        ready_jobs = [j for j in fake_queue.jobs if j["name"] == "send_receipt" and j["kwargs"]["event"] == "ready"]
        assert len(ready_jobs) == 1
        assert ready_jobs[0]["kwargs"]["order_id"] == oid

    async def test_processing_status_does_not_enqueue(self, client, fake_queue, token, order_via_api):
        oid = order_via_api["id"]
        fake_queue.clear()
        await client.post(f"/orders/{oid}/status", json={"to_status": "processing"}, headers=auth(token))
        assert not any(j["kwargs"].get("event") == "ready" for j in fake_queue.jobs)

    async def test_picked_up_status_does_not_enqueue_receipt(self, client, fake_queue, token, order_via_api):
        oid = order_via_api["id"]
        await client.post(f"/orders/{oid}/status", json={"to_status": "processing"}, headers=auth(token))
        await client.post(f"/orders/{oid}/status", json={"to_status": "ready"}, headers=auth(token))
        fake_queue.clear()
        await client.post(f"/orders/{oid}/status", json={"to_status": "picked_up"}, headers=auth(token))
        assert all(j["kwargs"].get("event") != "ready" for j in fake_queue.jobs)


# ---------------------------------------------------------------------------
# 2. Receipt builder — pure function, no DB
# ---------------------------------------------------------------------------


class TestBuildReceiptText:
    _receipt = Receipt(
        pickup_code="ABCD1234",
        customer_name="Adaeze Obi",
        customer_phone="08012345678",
        staff_name="Job Attendant",
        lines=(
            ReceiptLine("Wash & Fold", 2, 200_000),
            ReceiptLine("Ironing", 1, 50_000),
        ),
        total_kobo=250_000,
        paid_kobo=100_000,
        outstanding_kobo=150_000,
        event="paid",
    )

    def test_contains_pickup_code(self):
        assert "ABCD1234" in build_receipt_text(self._receipt)

    def test_contains_service_names(self):
        text = build_receipt_text(self._receipt)
        assert "Wash & Fold" in text
        assert "Ironing" in text

    def test_contains_piece_counts(self):
        text = build_receipt_text(self._receipt)
        assert "× 2" in text
        assert "× 1" in text

    def test_contains_line_totals(self):
        text = build_receipt_text(self._receipt)
        assert "₦2,000.00" in text   # 200_000 kobo
        assert "₦500.00" in text     # 50_000 kobo

    def test_contains_total_paid_balance(self):
        text = build_receipt_text(self._receipt)
        assert "₦2,500.00" in text   # total
        assert "₦1,000.00" in text   # paid
        assert "₦1,500.00" in text   # balance

    def test_contains_staff_name(self):
        assert "Job Attendant" in build_receipt_text(self._receipt)

    def test_paid_event_heading(self):
        assert "Payment Receipt" in build_receipt_text(self._receipt)

    def test_ready_event_heading(self):
        r = Receipt(**{**self._receipt.__dict__, "event": "ready"})
        assert "Order Ready" in build_receipt_text(r)

    def test_zero_balance_shown_correctly(self):
        r = Receipt(**{**self._receipt.__dict__, "paid_kobo": 250_000, "outstanding_kobo": 0})
        text = build_receipt_text(r)
        assert "₦0.00" in text

    def test_negative_balance_shown_correctly(self):
        """Overpayment should show negative balance (credit)."""
        r = Receipt(**{**self._receipt.__dict__, "paid_kobo": 300_000, "outstanding_kobo": -50_000})
        text = build_receipt_text(r)
        assert "-₦500.00" in text or "₦-500.00" in text or "−" in text or "-500" in text


# ---------------------------------------------------------------------------
# 3. Job execution — send_receipt() with fake provider + real test DB data
# ---------------------------------------------------------------------------


class TestSendReceiptJob:
    """Calls send_receipt() directly; injects db_session so the test transaction is visible."""

    @pytest.fixture
    async def order_data(self, db_session, branch, attendant, customer, wash_svc, iron_svc, rules):
        """Creates an order with two lines directly in the DB (no HTTP)."""
        order = Order(
            branch_id=branch.id,
            attendant_id=attendant.id,
            customer_id=customer.id,
            status="received",
            turnaround=Turnaround.regular,
            pickup_code="JOBTEST1",
            total_kobo=250_000,
        )
        db_session.add(order)
        await db_session.flush()

        lines = [
            OrderLine(order_id=order.id, service_id=wash_svc.id, piece_count=2,
                      unit_price_kobo=100_000, line_total_kobo=200_000),
            OrderLine(order_id=order.id, service_id=iron_svc.id, piece_count=1,
                      unit_price_kobo=50_000, line_total_kobo=50_000),
        ]
        for l in lines:
            db_session.add(l)
        await db_session.flush()
        return order

    async def test_sends_both_whatsapp_and_sms(self, db_session, order_data):
        provider = FakeNotificationProvider()
        ctx = {"notification_provider": provider, "db_session": db_session}
        await send_receipt(ctx, order_id=order_data.id, event="paid")
        assert len(provider.by_channel("whatsapp")) == 1
        assert len(provider.by_channel("sms")) == 1

    async def test_sent_to_customer_phone(self, db_session, order_data, customer):
        provider = FakeNotificationProvider()
        ctx = {"notification_provider": provider, "db_session": db_session}
        await send_receipt(ctx, order_id=order_data.id, event="paid")
        for msg in provider.sent:
            assert msg.phone == customer.phone

    async def test_receipt_includes_pickup_code(self, db_session, order_data):
        provider = FakeNotificationProvider()
        ctx = {"notification_provider": provider, "db_session": db_session}
        await send_receipt(ctx, order_id=order_data.id, event="paid")
        assert all("JOBTEST1" in m.message for m in provider.sent)

    async def test_receipt_includes_itemized_lines(self, db_session, order_data):
        provider = FakeNotificationProvider()
        ctx = {"notification_provider": provider, "db_session": db_session}
        await send_receipt(ctx, order_id=order_data.id, event="paid")
        text = provider.sent[0].message
        assert "Wash & Fold" in text
        assert "Ironing" in text

    async def test_receipt_reflects_partial_payment(self, db_session, order_data):
        # Add a partial payment
        pmt = Payment(order_id=order_data.id, amount_kobo=100_000, method=PaymentMethod.cash)
        db_session.add(pmt)
        await db_session.flush()

        provider = FakeNotificationProvider()
        ctx = {"notification_provider": provider, "db_session": db_session}
        await send_receipt(ctx, order_id=order_data.id, event="paid")
        text = provider.sent[0].message
        assert "₦1,000.00" in text  # paid = 100,000 kobo
        assert "₦1,500.00" in text  # balance = 150,000 kobo

    async def test_receipt_ready_event_heading(self, db_session, order_data):
        provider = FakeNotificationProvider()
        ctx = {"notification_provider": provider, "db_session": db_session}
        await send_receipt(ctx, order_id=order_data.id, event="ready")
        assert all("Order Ready" in m.message for m in provider.sent)

    async def test_silently_skips_deleted_order(self, db_session):
        provider = FakeNotificationProvider()
        ctx = {"notification_provider": provider, "db_session": db_session}
        await send_receipt(ctx, order_id="00000000-0000-0000-0000-000000000000", event="paid")
        assert provider.sent == []

    async def test_receipt_includes_staff_name(self, db_session, order_data, attendant):
        provider = FakeNotificationProvider()
        ctx = {"notification_provider": provider, "db_session": db_session}
        await send_receipt(ctx, order_id=order_data.id, event="paid")
        assert all(attendant.name in m.message for m in provider.sent)
