"""
Integration tests for POST /branches/{branch_id}/orders.

All pricing assertions use exact kobo values derived from the same
integer arithmetic as the engine, so they serve as regression guards.
"""

import pytest
from httpx import AsyncClient

from app.models.branch import Branch
from app.models.customer import Customer
from app.models.order import Turnaround
from app.models.organization import Organization
from app.models.price_rule import PriceRule
from app.models.service import Service
from app.models.staff import Staff, StaffRole
from app.services.auth import create_access_token, hash_password


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def org(db_session):
    o = Organization(name="Orders Test Org")
    db_session.add(o)
    await db_session.flush()
    return o


@pytest.fixture
async def branch(db_session, org):
    b = Branch(name="Test Branch", organization_id=org.id)
    db_session.add(b)
    await db_session.flush()
    return b


@pytest.fixture
async def attendant(db_session, branch):
    s = Staff(
        name="Test Attendant",
        email="orders_attendant@test.com",
        role=StaffRole.attendant,
        branch_id=branch.id,
        password_hash=hash_password("pass"),
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
def attendant_token(attendant):
    return create_access_token(attendant.id, attendant.role.value, attendant.branch_id)


@pytest.fixture
async def customer_tier1(db_session):
    c = Customer(name="Tier 1 Customer", phone="08031110001", tier=1)
    db_session.add(c)
    await db_session.flush()
    return c


@pytest.fixture
async def customer_tier2(db_session):
    c = Customer(name="Tier 2 Customer", phone="08031110002", tier=2)
    db_session.add(c)
    await db_session.flush()
    return c


@pytest.fixture
async def wash_service(db_session):
    s = Service(name="Wash")
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def iron_service(db_session):
    s = Service(name="Iron")
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def price_rules(db_session, wash_service, iron_service):
    """Create price rules for tiers 1 and 2 for both services."""
    rules = [
        PriceRule(service_id=wash_service.id, tier=1, price_kobo=100_000),
        PriceRule(service_id=wash_service.id, tier=2, price_kobo=150_000),
        PriceRule(service_id=iron_service.id, tier=1, price_kobo=50_000),
        PriceRule(service_id=iron_service.id, tier=2, price_kobo=75_000),
    ]
    for r in rules:
        db_session.add(r)
    await db_session.flush()
    return rules


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Happy path — single line
# ---------------------------------------------------------------------------


async def test_create_order_single_line_regular(
    client: AsyncClient, branch, attendant_token, customer_tier1, price_rules, wash_service
):
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": customer_tier1.id,
            "turnaround": "regular",
            "lines": [{"service_id": wash_service.id, "piece_count": 3}],
        },
        headers=auth(attendant_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    # 100_000 × 3 × 1 = 300_000
    assert data["total_kobo"] == 300_000
    assert data["turnaround"] == "regular"
    assert data["status"] == "received"
    assert data["version"] == 1
    assert len(data["pickup_code"]) == 8
    assert len(data["lines"]) == 1
    assert data["lines"][0]["unit_price_kobo"] == 100_000
    assert data["lines"][0]["line_total_kobo"] == 300_000
    assert data["lines"][0]["piece_count"] == 3


async def test_create_order_single_line_express(
    client: AsyncClient, branch, attendant_token, customer_tier1, price_rules, wash_service
):
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": customer_tier1.id,
            "turnaround": "express",
            "lines": [{"service_id": wash_service.id, "piece_count": 2}],
        },
        headers=auth(attendant_token),
    )
    assert resp.status_code == 201
    # 100_000 × 2 × 1.5 = 300_000 (exact)
    assert resp.json()["total_kobo"] == 300_000


async def test_create_order_single_line_same_day(
    client: AsyncClient, branch, attendant_token, customer_tier1, price_rules, wash_service
):
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": customer_tier1.id,
            "turnaround": "same_day",
            "lines": [{"service_id": wash_service.id, "piece_count": 1}],
        },
        headers=auth(attendant_token),
    )
    assert resp.status_code == 201
    # 100_000 × 1 × 3 = 300_000
    assert resp.json()["total_kobo"] == 300_000


# ---------------------------------------------------------------------------
# Happy path — multi-line
# ---------------------------------------------------------------------------


async def test_create_order_multi_line_regular(
    client: AsyncClient, branch, attendant_token, customer_tier1,
    price_rules, wash_service, iron_service
):
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": customer_tier1.id,
            "turnaround": "regular",
            "lines": [
                {"service_id": wash_service.id, "piece_count": 2},
                {"service_id": iron_service.id, "piece_count": 5},
            ],
        },
        headers=auth(attendant_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    # wash: 100_000 × 2 = 200_000
    # iron: 50_000 × 5 = 250_000
    # total: 450_000
    assert data["total_kobo"] == 450_000
    assert len(data["lines"]) == 2


async def test_create_order_multi_line_express_pricing(
    client: AsyncClient, branch, attendant_token, customer_tier1,
    price_rules, wash_service, iron_service
):
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": customer_tier1.id,
            "turnaround": "express",
            "lines": [
                {"service_id": wash_service.id, "piece_count": 1},
                {"service_id": iron_service.id, "piece_count": 1},
            ],
        },
        headers=auth(attendant_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    # wash: 100_000 × 1 × 1.5 = 150_000 (exact)
    # iron:  50_000 × 1 × 1.5 =  75_000 (exact)
    # total: 225_000
    assert data["total_kobo"] == 225_000
    lines_by_service = {l["service_id"]: l for l in data["lines"]}
    assert lines_by_service[wash_service.id]["line_total_kobo"] == 150_000
    assert lines_by_service[iron_service.id]["line_total_kobo"] == 75_000


# ---------------------------------------------------------------------------
# Tier pricing
# ---------------------------------------------------------------------------


async def test_tier2_customer_gets_higher_price(
    client: AsyncClient, branch, attendant_token, customer_tier2,
    price_rules, wash_service
):
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": customer_tier2.id,
            "turnaround": "regular",
            "lines": [{"service_id": wash_service.id, "piece_count": 1}],
        },
        headers=auth(attendant_token),
    )
    assert resp.status_code == 201
    # tier-2 wash = 150_000 per piece
    assert resp.json()["total_kobo"] == 150_000


# ---------------------------------------------------------------------------
# Server recomputes — client cannot influence total
# ---------------------------------------------------------------------------


async def test_server_ignores_extra_fields_and_recomputes(
    client: AsyncClient, branch, attendant_token, customer_tier1,
    price_rules, wash_service
):
    """Client cannot send a price. The schema rejects unknown fields by default,
    and the total is always derived from PriceRules server-side."""
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": customer_tier1.id,
            "turnaround": "regular",
            "lines": [{"service_id": wash_service.id, "piece_count": 1}],
            "total_kobo": 1,   # attacker tries to set their own total
        },
        headers=auth(attendant_token),
    )
    assert resp.status_code == 201
    # Server ignored the hint and computed the real total
    assert resp.json()["total_kobo"] == 100_000


# ---------------------------------------------------------------------------
# Pickup code
# ---------------------------------------------------------------------------


async def test_pickup_code_is_8_chars_alphanumeric(
    client: AsyncClient, branch, attendant_token, customer_tier1,
    price_rules, wash_service
):
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": customer_tier1.id,
            "turnaround": "regular",
            "lines": [{"service_id": wash_service.id, "piece_count": 1}],
        },
        headers=auth(attendant_token),
    )
    code = resp.json()["pickup_code"]
    assert len(code) == 8
    assert code.isalnum()
    assert code.isupper()


async def test_two_orders_have_different_pickup_codes(
    client: AsyncClient, branch, attendant_token, customer_tier1,
    price_rules, wash_service
):
    body = {
        "customer_id": customer_tier1.id,
        "turnaround": "regular",
        "lines": [{"service_id": wash_service.id, "piece_count": 1}],
    }
    r1 = await client.post(f"/branches/{branch.id}/orders", json=body, headers=auth(attendant_token))
    r2 = await client.post(f"/branches/{branch.id}/orders", json=body, headers=auth(attendant_token))
    assert r1.json()["pickup_code"] != r2.json()["pickup_code"]


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


async def test_missing_price_rule_returns_422(
    client: AsyncClient, branch, attendant_token, customer_tier1
):
    """No PriceRule exists for this service → 422."""
    service_without_rule = Service(name="No-Rule Service")
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": customer_tier1.id,
            "turnaround": "regular",
            "lines": [{"service_id": "nonexistent-service-id", "piece_count": 1}],
        },
        headers=auth(attendant_token),
    )
    assert resp.status_code == 422
    assert "price rule" in resp.json()["detail"].lower()


async def test_customer_not_found_returns_404(
    client: AsyncClient, branch, attendant_token, price_rules, wash_service
):
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": "00000000-0000-0000-0000-000000000000",
            "turnaround": "regular",
            "lines": [{"service_id": wash_service.id, "piece_count": 1}],
        },
        headers=auth(attendant_token),
    )
    assert resp.status_code == 404


async def test_empty_lines_rejected_by_schema(
    client: AsyncClient, branch, attendant_token, customer_tier1
):
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": customer_tier1.id,
            "turnaround": "regular",
            "lines": [],
        },
        headers=auth(attendant_token),
    )
    assert resp.status_code == 422


async def test_zero_piece_count_rejected_by_schema(
    client: AsyncClient, branch, attendant_token, customer_tier1, wash_service
):
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": customer_tier1.id,
            "turnaround": "regular",
            "lines": [{"service_id": wash_service.id, "piece_count": 0}],
        },
        headers=auth(attendant_token),
    )
    assert resp.status_code == 422


async def test_invalid_turnaround_rejected(
    client: AsyncClient, branch, attendant_token, customer_tier1, wash_service
):
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": customer_tier1.id,
            "turnaround": "next_week",
            "lines": [{"service_id": wash_service.id, "piece_count": 1}],
        },
        headers=auth(attendant_token),
    )
    assert resp.status_code == 422


async def test_unauthenticated_request_rejected(
    client: AsyncClient, branch, customer_tier1, wash_service
):
    resp = await client.post(
        f"/branches/{branch.id}/orders",
        json={
            "customer_id": customer_tier1.id,
            "turnaround": "regular",
            "lines": [{"service_id": wash_service.id, "piece_count": 1}],
        },
    )
    assert resp.status_code == 401


async def test_attendant_cannot_create_order_for_other_branch(
    client: AsyncClient, branch, customer_tier1, price_rules, wash_service, db_session, org
):
    """Branch-guard: attendant from branch A cannot POST to branch B."""
    other_branch = Branch(name="Other Branch", organization_id=org.id)
    db_session.add(other_branch)
    await db_session.flush()

    other_attendant = Staff(
        name="Other Attendant",
        email="other_orders@test.com",
        role=StaffRole.attendant,
        branch_id=branch.id,
        password_hash=hash_password("pass"),
    )
    db_session.add(other_attendant)
    await db_session.flush()

    token = create_access_token(other_attendant.id, other_attendant.role.value, other_attendant.branch_id)

    resp = await client.post(
        f"/branches/{other_branch.id}/orders",
        json={
            "customer_id": customer_tier1.id,
            "turnaround": "regular",
            "lines": [{"service_id": wash_service.id, "piece_count": 1}],
        },
        headers=auth(token),
    )
    assert resp.status_code == 403
