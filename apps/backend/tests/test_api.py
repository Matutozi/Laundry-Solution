"""
Integration tests for the full REST API surface.

Covers:
  - Customer create / search
  - Order creation (pricing wired in)
  - Payment append-only with balance carry-forward
  - Forward-only status transitions (illegal backward moves rejected)
  - Pickup-by-code lookup and release
"""

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
from app.services.status import InvalidTransitionError, validate_transition


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def org(db_session):
    o = Organization(name="API Test Org")
    db_session.add(o)
    await db_session.flush()
    return o


@pytest.fixture
async def branch(db_session, org):
    b = Branch(name="API Branch", organization_id=org.id)
    db_session.add(b)
    await db_session.flush()
    return b


@pytest.fixture
async def attendant(db_session, branch):
    s = Staff(
        name="API Attendant", email="api_attendant@test.com",
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
async def wash_service(db_session):
    s = Service(name="API Wash")
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def iron_service(db_session):
    s = Service(name="API Iron")
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def price_rules(db_session, wash_service, iron_service):
    rows = [
        PriceRule(service_id=wash_service.id, tier=1, price_kobo=100_000),
        PriceRule(service_id=wash_service.id, tier=2, price_kobo=150_000),
        PriceRule(service_id=iron_service.id, tier=1, price_kobo=50_000),
    ]
    for r in rows:
        db_session.add(r)
    await db_session.flush()
    return rows


@pytest.fixture
async def customer(db_session):
    c = Customer(name="API Customer", phone="08099001111", tier=1)
    db_session.add(c)
    await db_session.flush()
    return c


@pytest.fixture
async def placed_order(client, branch, token, customer, price_rules, wash_service):
    """A freshly placed order: 2 × wash @ tier-1 regular = 200,000 kobo."""
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": customer.id,
            "turnaround": "regular",
            "lines": [{"service_id": wash_service.id, "piece_count": 2}],
        },
        headers=auth(token),
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Customer create / search
# ---------------------------------------------------------------------------


async def test_create_customer(client: AsyncClient, token):
    resp = await client.post(
        "/customers",
        json={"name": "Ngozi Adeyemi", "phone": "08011223344", "tier": 2},
        headers=auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Ngozi Adeyemi"
    assert data["phone"] == "08011223344"
    assert data["tier"] == 2
    assert "id" in data


async def test_duplicate_phone_returns_409(client: AsyncClient, token):
    body = {"name": "First", "phone": "08022334455", "tier": 1}
    await client.post("/customers", json=body, headers=auth(token))
    resp = await client.post("/customers", json=body, headers=auth(token))
    assert resp.status_code == 409


async def test_search_customer_by_phone(client: AsyncClient, token):
    await client.post("/customers", json={"name": "Search Phone", "phone": "08033445566", "tier": 1}, headers=auth(token))
    resp = await client.get("/customers?q=08033445566", headers=auth(token))
    assert resp.status_code == 200
    assert any(c["phone"] == "08033445566" for c in resp.json())


async def test_search_customer_by_name(client: AsyncClient, token):
    await client.post("/customers", json={"name": "Unique Emeka", "phone": "08044556677", "tier": 1}, headers=auth(token))
    resp = await client.get("/customers?q=Unique+Emeka", headers=auth(token))
    assert resp.status_code == 200
    assert any("Emeka" in c["name"] for c in resp.json())


async def test_search_no_results(client: AsyncClient, token):
    resp = await client.get("/customers?q=ZZZDoesNotExist", headers=auth(token))
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Order happy path
# ---------------------------------------------------------------------------


async def test_placed_order_has_correct_total(placed_order):
    # 2 × 100,000 regular = 200,000
    assert placed_order["total_kobo"] == 200_000
    assert placed_order["status"] == "received"
    assert placed_order["version"] == 1


async def test_get_order_by_id(client: AsyncClient, token, placed_order):
    resp = await client.get(f"/orders/{placed_order['id']}", headers=auth(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == placed_order["id"]


# ---------------------------------------------------------------------------
# Payment — append-only with balance carry-forward
# ---------------------------------------------------------------------------


async def test_full_payment_zeroes_balance(client: AsyncClient, token, placed_order):
    resp = await client.post(
        f"/orders/{placed_order['id']}/payments",
        json={"amount_kobo": 200_000, "method": "cash"},
        headers=auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["outstanding_kobo"] == 0


async def test_part_payment_carries_balance(client: AsyncClient, token, placed_order):
    # Order total = 200,000 kobo
    # Pay 60,000 → outstanding 140,000
    r1 = await client.post(
        f"/orders/{placed_order['id']}/payments",
        json={"amount_kobo": 60_000, "method": "cash"},
        headers=auth(token),
    )
    assert r1.status_code == 201
    assert r1.json()["outstanding_kobo"] == 140_000

    # Pay 80,000 → outstanding 60,000
    r2 = await client.post(
        f"/orders/{placed_order['id']}/payments",
        json={"amount_kobo": 80_000, "method": "transfer"},
        headers=auth(token),
    )
    assert r2.status_code == 201
    assert r2.json()["outstanding_kobo"] == 60_000

    # Pay remaining 60,000 → outstanding 0
    r3 = await client.post(
        f"/orders/{placed_order['id']}/payments",
        json={"amount_kobo": 60_000, "method": "pos"},
        headers=auth(token),
    )
    assert r3.status_code == 201
    assert r3.json()["outstanding_kobo"] == 0


async def test_overpayment_shows_negative_balance(client: AsyncClient, token, placed_order):
    resp = await client.post(
        f"/orders/{placed_order['id']}/payments",
        json={"amount_kobo": 250_000, "method": "cash"},
        headers=auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["outstanding_kobo"] == -50_000


async def test_zero_payment_rejected(client: AsyncClient, token, placed_order):
    resp = await client.post(
        f"/orders/{placed_order['id']}/payments",
        json={"amount_kobo": 0, "method": "cash"},
        headers=auth(token),
    )
    assert resp.status_code == 422


async def test_payment_on_nonexistent_order_returns_404(client: AsyncClient, token):
    resp = await client.post(
        "/orders/00000000-0000-0000-0000-000000000000/payments",
        json={"amount_kobo": 1000, "method": "cash"},
        headers=auth(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Status transitions — forward-only
# ---------------------------------------------------------------------------


class TestValidateTransition:
    """Pure-function unit tests for the transition guard — no DB."""

    def test_received_to_processing_allowed(self):
        validate_transition(OrderStatus.received, OrderStatus.processing)

    def test_processing_to_ready_allowed(self):
        validate_transition(OrderStatus.processing, OrderStatus.ready)

    def test_ready_to_picked_up_allowed(self):
        validate_transition(OrderStatus.ready, OrderStatus.picked_up)

    def test_ready_to_delivered_allowed(self):
        validate_transition(OrderStatus.ready, OrderStatus.delivered)

    def test_backward_move_raises(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition(OrderStatus.processing, OrderStatus.received)

    def test_skip_forward_raises(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition(OrderStatus.received, OrderStatus.ready)

    def test_terminal_state_raises(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition(OrderStatus.picked_up, OrderStatus.received)


async def test_status_forward_pipeline(client: AsyncClient, token, placed_order):
    oid = placed_order["id"]

    r1 = await client.post(f"/orders/{oid}/status", json={"to_status": "processing"}, headers=auth(token))
    assert r1.status_code == 200
    assert r1.json()["to_status"] == "processing"
    assert r1.json()["version"] == 2

    r2 = await client.post(f"/orders/{oid}/status", json={"to_status": "ready"}, headers=auth(token))
    assert r2.status_code == 200
    assert r2.json()["version"] == 3

    r3 = await client.post(f"/orders/{oid}/status", json={"to_status": "picked_up"}, headers=auth(token))
    assert r3.status_code == 200
    assert r3.json()["version"] == 4


async def test_illegal_backward_move_rejected(client: AsyncClient, token, placed_order):
    oid = placed_order["id"]
    # Advance to processing
    await client.post(f"/orders/{oid}/status", json={"to_status": "processing"}, headers=auth(token))
    # Try to go back to received — must be rejected
    resp = await client.post(f"/orders/{oid}/status", json={"to_status": "received"}, headers=auth(token))
    assert resp.status_code == 422
    assert "received" in resp.json()["detail"].lower()


async def test_skip_forward_rejected(client: AsyncClient, token, placed_order):
    oid = placed_order["id"]
    # Try to jump directly received → ready (skipping processing)
    resp = await client.post(f"/orders/{oid}/status", json={"to_status": "ready"}, headers=auth(token))
    assert resp.status_code == 422


async def test_transition_from_terminal_state_rejected(client: AsyncClient, token, placed_order):
    oid = placed_order["id"]
    await client.post(f"/orders/{oid}/status", json={"to_status": "processing"}, headers=auth(token))
    await client.post(f"/orders/{oid}/status", json={"to_status": "ready"}, headers=auth(token))
    await client.post(f"/orders/{oid}/status", json={"to_status": "picked_up"}, headers=auth(token))
    # picked_up is terminal — any further move must fail
    resp = await client.post(f"/orders/{oid}/status", json={"to_status": "delivered"}, headers=auth(token))
    assert resp.status_code == 422


async def test_each_transition_bumps_version(client: AsyncClient, token, placed_order):
    oid = placed_order["id"]
    assert placed_order["version"] == 1
    for step, expected_status in enumerate(["processing", "ready", "delivered"], start=2):
        r = await client.post(f"/orders/{oid}/status", json={"to_status": expected_status}, headers=auth(token))
        assert r.json()["version"] == step


# ---------------------------------------------------------------------------
# Pickup by code
# ---------------------------------------------------------------------------


async def test_pickup_lookup_returns_order(client: AsyncClient, token, placed_order):
    code = placed_order["pickup_code"]
    resp = await client.get(f"/pickup/{code}", headers=auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["pickup_code"] == code
    assert data["total_kobo"] == 200_000
    assert data["outstanding_kobo"] == 200_000  # nothing paid yet
    assert data["paid_kobo"] == 0


async def test_pickup_lookup_reflects_payments(client: AsyncClient, token, placed_order):
    oid = placed_order["id"]
    code = placed_order["pickup_code"]
    await client.post(f"/orders/{oid}/payments", json={"amount_kobo": 120_000, "method": "cash"}, headers=auth(token))
    resp = await client.get(f"/pickup/{code}", headers=auth(token))
    assert resp.json()["paid_kobo"] == 120_000
    assert resp.json()["outstanding_kobo"] == 80_000


async def test_pickup_release_transitions_to_picked_up(client: AsyncClient, token, placed_order):
    oid = placed_order["id"]
    code = placed_order["pickup_code"]
    # Must be in ready state first
    await client.post(f"/orders/{oid}/status", json={"to_status": "processing"}, headers=auth(token))
    await client.post(f"/orders/{oid}/status", json={"to_status": "ready"}, headers=auth(token))

    resp = await client.post(f"/pickup/{code}/release", headers=auth(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "picked_up"


async def test_pickup_release_from_non_ready_rejected(client: AsyncClient, token, placed_order):
    """Order is still in 'received' — release must fail."""
    code = placed_order["pickup_code"]
    resp = await client.post(f"/pickup/{code}/release", headers=auth(token))
    assert resp.status_code == 422


async def test_pickup_invalid_code_returns_404(client: AsyncClient, token):
    resp = await client.get("/pickup/XXXXXXXX", headers=auth(token))
    assert resp.status_code == 404
