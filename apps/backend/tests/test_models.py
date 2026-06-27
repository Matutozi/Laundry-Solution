"""Integration tests for the full entity graph, relationships, and DB constraints."""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    Branch,
    Customer,
    Order,
    OrderLine,
    OrderStatus,
    Organization,
    Payment,
    PaymentMethod,
    PriceRule,
    Service,
    Staff,
    StaffRole,
    StatusEvent,
)
from app.models.order import Turnaround


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def org(db_session):
    org = Organization(name="Wise-Wash HQ")
    db_session.add(org)
    await db_session.flush()
    return org


@pytest.fixture
async def branch(db_session, org):
    b = Branch(name="Lagos Island", organization_id=org.id)
    db_session.add(b)
    await db_session.flush()
    return b


@pytest.fixture
async def attendant(db_session, branch):
    s = Staff(name="Amaka", email="amaka@test.com", role=StaffRole.attendant, branch_id=branch.id)
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def customer(db_session):
    c = Customer(name="Chidi Okeke", phone="08012345678", tier=2)
    db_session.add(c)
    await db_session.flush()
    return c


@pytest.fixture
async def service(db_session):
    svc = Service(name="Dry Cleaning")
    db_session.add(svc)
    await db_session.flush()
    return svc


@pytest.fixture
async def price_rule(db_session, service):
    pr = PriceRule(service_id=service.id, tier=2, price_kobo=150_000)
    db_session.add(pr)
    await db_session.flush()
    return pr


@pytest.fixture
async def order(db_session, branch, attendant, customer):
    o = Order(
        branch_id=branch.id,
        attendant_id=attendant.id,
        customer_id=customer.id,
        pickup_code="PICK-001",
        turnaround=Turnaround.regular,
        total_kobo=0,
    )
    db_session.add(o)
    await db_session.flush()
    return o


# ---------------------------------------------------------------------------
# Relationship tests
# ---------------------------------------------------------------------------


async def test_org_branch_relationship(db_session, org, branch):
    result = await db_session.execute(
        select(Organization).where(Organization.id == org.id)
    )
    loaded = result.scalar_one()
    await db_session.refresh(loaded, ["branches"])
    assert len(loaded.branches) == 1
    assert loaded.branches[0].name == "Lagos Island"


async def test_branch_staff_relationship(db_session, branch, attendant):
    await db_session.refresh(branch, ["staff"])
    assert len(branch.staff) == 1
    assert branch.staff[0].role == StaffRole.attendant


async def test_order_full_graph(db_session, order, service, price_rule):
    line = OrderLine(
        order_id=order.id, service_id=service.id, piece_count=3,
        unit_price_kobo=150_000, line_total_kobo=450_000,
    )
    db_session.add(line)

    payment = Payment(
        order_id=order.id, amount_kobo=450_000, method=PaymentMethod.cash
    )
    db_session.add(payment)

    event = StatusEvent(
        order_id=order.id,
        staff_id=order.attendant_id,
        from_status=OrderStatus.received,
        to_status=OrderStatus.processing,
    )
    db_session.add(event)
    await db_session.flush()

    await db_session.refresh(order, ["lines", "payments", "status_events"])
    assert len(order.lines) == 1
    assert order.lines[0].piece_count == 3
    assert len(order.payments) == 1
    assert order.payments[0].amount_kobo == 450_000
    assert len(order.status_events) == 1
    assert order.status_events[0].to_status == OrderStatus.processing


async def test_order_version_default(db_session, order):
    assert order.version == 1


async def test_price_rule_stored_as_kobo(db_session, price_rule):
    result = await db_session.execute(
        select(PriceRule).where(PriceRule.id == price_rule.id)
    )
    loaded = result.scalar_one()
    assert isinstance(loaded.price_kobo, int)
    assert loaded.price_kobo == 150_000


# ---------------------------------------------------------------------------
# Constraint tests
# ---------------------------------------------------------------------------


async def test_customer_tier_constraint(db_session):
    bad = Customer(name="Bad Tier", phone="08099999999", tier=5)
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_price_rule_unique_service_tier(db_session, service, price_rule):
    duplicate = PriceRule(service_id=service.id, tier=2, price_kobo=200_000)
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_price_rule_tier_constraint(db_session, service):
    bad = PriceRule(service_id=service.id, tier=0, price_kobo=100_000)
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_order_line_piece_count_positive(db_session, order, service):
    bad = OrderLine(order_id=order.id, service_id=service.id, piece_count=0)
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_payment_amount_positive(db_session, order):
    bad = Payment(order_id=order.id, amount_kobo=0, method=PaymentMethod.cash)
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_customer_phone_unique(db_session, customer):
    dup = Customer(name="Duplicate", phone=customer.phone, tier=1)
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_pickup_code_unique(db_session, order, branch, attendant, customer):
    dup = Order(
        branch_id=branch.id,
        attendant_id=attendant.id,
        customer_id=customer.id,
        pickup_code="PICK-001",  # same as the fixture order
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
