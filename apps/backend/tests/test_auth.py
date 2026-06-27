"""Integration tests for JWT auth, role guards, and branch scoping."""
import pytest
from httpx import AsyncClient

from app.models.branch import Branch
from app.models.customer import Customer
from app.models.order import Order, Turnaround
from app.models.organization import Organization
from app.models.staff import Staff, StaffRole
from app.services.auth import create_access_token, hash_password, hash_pin


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def org(db_session):
    o = Organization(name="Auth Test Org")
    db_session.add(o)
    await db_session.flush()
    return o


@pytest.fixture
async def branch_a(db_session, org):
    b = Branch(name="Branch A", organization_id=org.id)
    db_session.add(b)
    await db_session.flush()
    return b


@pytest.fixture
async def branch_b(db_session, org):
    b = Branch(name="Branch B", organization_id=org.id)
    db_session.add(b)
    await db_session.flush()
    return b


@pytest.fixture
async def attendant_a(db_session, branch_a):
    s = Staff(
        name="Attendant A",
        email="attendant_a@test.com",
        role=StaffRole.attendant,
        branch_id=branch_a.id,
        password_hash=hash_password("secret123"),
        pin_hash=hash_pin("1234"),
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def attendant_b(db_session, branch_b):
    s = Staff(
        name="Attendant B",
        email="attendant_b@test.com",
        role=StaffRole.attendant,
        branch_id=branch_b.id,
        password_hash=hash_password("secret123"),
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def manager(db_session, branch_a):
    s = Staff(
        name="Manager",
        email="manager@test.com",
        role=StaffRole.manager,
        branch_id=branch_a.id,
        password_hash=hash_password("manager_pass"),
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def order_in_branch_b(db_session, branch_b, attendant_b):
    customer = Customer(name="Test Customer", phone="08011112222", tier=1)
    db_session.add(customer)
    await db_session.flush()
    o = Order(
        branch_id=branch_b.id,
        attendant_id=attendant_b.id,
        customer_id=customer.id,
        pickup_code="AUTH-TEST-001",
        turnaround=Turnaround.regular,
        total_kobo=0,
    )
    db_session.add(o)
    await db_session.flush()
    return o


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------


async def test_valid_login_returns_token(client: AsyncClient, attendant_a):
    response = await client.post("/auth/login", json={
        "email": "attendant_a@test.com",
        "password": "secret123",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 20


async def test_wrong_password_rejected(client: AsyncClient, attendant_a):
    response = await client.post("/auth/login", json={
        "email": "attendant_a@test.com",
        "password": "wrong_password",
    })
    assert response.status_code == 401


async def test_unknown_email_rejected(client: AsyncClient):
    response = await client.post("/auth/login", json={
        "email": "nobody@test.com",
        "password": "doesnt_matter",
    })
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PIN re-auth tests
# ---------------------------------------------------------------------------


async def test_valid_pin_returns_token(client: AsyncClient, attendant_a):
    response = await client.post("/auth/pin", json={
        "staff_id": attendant_a.id,
        "pin": "1234",
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_wrong_pin_rejected(client: AsyncClient, attendant_a):
    response = await client.post("/auth/pin", json={
        "staff_id": attendant_a.id,
        "pin": "9999",
    })
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Role guard tests
# ---------------------------------------------------------------------------


async def test_attendant_cannot_access_manager_endpoint(client: AsyncClient, attendant_a, branch_a):
    token = create_access_token(attendant_a.id, attendant_a.role.value, attendant_a.branch_id)
    response = await client.get(
        f"/branches/{branch_a.id}/report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_manager_can_access_manager_endpoint(client: AsyncClient, manager, branch_a):
    token = create_access_token(manager.id, manager.role.value, manager.branch_id)
    response = await client.get(
        f"/branches/{branch_a.id}/report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


async def test_no_token_rejected(client: AsyncClient, branch_a):
    response = await client.get(f"/branches/{branch_a.id}/orders")
    assert response.status_code == 401


async def test_invalid_token_rejected(client: AsyncClient, branch_a):
    response = await client.get(
        f"/branches/{branch_a.id}/orders",
        headers={"Authorization": "Bearer not.a.valid.token"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Branch scoping tests
# ---------------------------------------------------------------------------


async def test_attendant_can_access_own_branch_orders(client: AsyncClient, attendant_a, branch_a):
    token = create_access_token(attendant_a.id, attendant_a.role.value, attendant_a.branch_id)
    response = await client.get(
        f"/branches/{branch_a.id}/orders",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


async def test_attendant_cannot_access_other_branch_orders(
    client: AsyncClient, attendant_a, branch_b, order_in_branch_b
):
    token = create_access_token(attendant_a.id, attendant_a.role.value, attendant_a.branch_id)
    response = await client.get(
        f"/branches/{branch_b.id}/orders",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_manager_can_access_any_branch_orders(
    client: AsyncClient, manager, branch_b, order_in_branch_b
):
    token = create_access_token(manager.id, manager.role.value, manager.branch_id)
    response = await client.get(
        f"/branches/{branch_b.id}/orders",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert any(o["pickup_code"] == "AUTH-TEST-001" for o in data)
