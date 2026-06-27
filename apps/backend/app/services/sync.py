"""WatermelonDB sync service — pure business logic, no HTTP.

Pull: return all records with server_seq > since (client's last known seq).
Push: apply client changes with these conflict rules:
  - Payments      → append-only; skip if ID already exists (idempotent).
  - Order status  → furthest-along wins; backward moves are silently ignored.
  - Money totals  → always recomputed server-side; client value ignored.
  - Ordering      → server_seq (monotonic counter), never device clocks.
  - Pickup codes  → offline codes are accepted if unique; collisions get
                    a freshly generated code and the mapping is returned
                    to the client so it can update its local record.
"""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.order import Order, OrderStatus, Turnaround
from app.models.order_line import OrderLine
from app.models.payment import Payment
from app.services.orders import load_price_rules
from app.services.pricing import OrderLineInput, price_order

# ─────────────────────────────────────────────
# Status pipeline ordering
# ─────────────────────────────────────────────

_STATUS_RANK: dict[OrderStatus, int] = {
    OrderStatus.received:   0,
    OrderStatus.processing: 1,
    OrderStatus.ready:      2,
    OrderStatus.picked_up:  3,
    OrderStatus.delivered:  3,
    OrderStatus.cancelled:  4,
}


def furthest_status(a: OrderStatus, b: OrderStatus) -> OrderStatus:
    """Return whichever status is furthest along in the pipeline."""
    return a if _STATUS_RANK[a] >= _STATUS_RANK[b] else b


# ─────────────────────────────────────────────
# Sequence helper
# ─────────────────────────────────────────────


async def _next_seq(db: AsyncSession) -> int:
    return (await db.execute(text("SELECT nextval('sync_global_seq')"))).scalar()


async def _current_max_seq(db: AsyncSession) -> int:
    """Return the highest server_seq across all synced tables (0 if none)."""
    result = await db.execute(text("""
        SELECT GREATEST(
            COALESCE((SELECT MAX(server_seq) FROM orders), 0),
            COALESCE((SELECT MAX(server_seq) FROM payments), 0),
            COALESCE((SELECT MAX(server_seq) FROM customers), 0)
        )
    """))
    return result.scalar() or 0


# ─────────────────────────────────────────────
# Offline pickup code
# ─────────────────────────────────────────────

_ALPHA = string.ascii_uppercase + string.digits


def offline_pickup_code(branch_id: str, device_id: str) -> str:
    """
    Build a pickup code that embeds branch and device identity so that two
    offline devices from the same branch cannot generate the same code without
    an astronomically unlikely random collision.

    Format: <3 branch hex chars><3 device hex chars><5 random chars>  →  11 chars total.
    """
    branch_prefix = branch_id.replace("-", "")[:3].upper()
    device_prefix = device_id.replace("-", "")[:3].upper()
    random_part = "".join(secrets.choice(_ALPHA) for _ in range(5))
    return f"{branch_prefix}{device_prefix}{random_part}"


def _fresh_code() -> str:
    return "".join(secrets.choice(_ALPHA) for _ in range(11))


# ─────────────────────────────────────────────
# Pull
# ─────────────────────────────────────────────


@dataclass
class PullResult:
    orders: list[dict]
    payments: list[dict]
    customers: list[dict]
    server_seq: int


def _order_dict(o: Order) -> dict:
    return {
        "id": o.id,
        "branch_id": o.branch_id,
        "attendant_id": o.attendant_id,
        "customer_id": o.customer_id,
        "status": o.status.value,
        "turnaround": o.turnaround.value,
        "pickup_code": o.pickup_code,
        "total_kobo": o.total_kobo,
        "version": o.version,
        "server_seq": o.server_seq,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }


def _payment_dict(p: Payment) -> dict:
    return {
        "id": p.id,
        "order_id": p.order_id,
        "amount_kobo": p.amount_kobo,
        "method": p.method.value,
        "recorded_at": p.recorded_at.isoformat() if p.recorded_at else None,
        "server_seq": p.server_seq,
    }


def _customer_dict(c: Customer) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "phone": c.phone,
        "tier": c.tier,
        "server_seq": c.server_seq,
    }


async def pull(since: int, db: AsyncSession) -> PullResult:
    """Return every record whose server_seq is greater than `since`."""
    orders = (await db.execute(
        select(Order).where(Order.server_seq > since).order_by(Order.server_seq)
    )).scalars().all()

    payments = (await db.execute(
        select(Payment).where(Payment.server_seq > since).order_by(Payment.server_seq)
    )).scalars().all()

    customers = (await db.execute(
        select(Customer).where(Customer.server_seq > since).order_by(Customer.server_seq)
    )).scalars().all()

    server_seq = await _current_max_seq(db)

    return PullResult(
        orders=[_order_dict(o) for o in orders],
        payments=[_payment_dict(p) for p in payments],
        customers=[_customer_dict(c) for c in customers],
        server_seq=server_seq,
    )


# ─────────────────────────────────────────────
# Push — per-entity helpers
# ─────────────────────────────────────────────


async def _push_customer(data: dict, db: AsyncSession) -> None:
    """Upsert a customer. Phone is the idempotency key for creates."""
    existing = await db.get(Customer, data["id"])
    if existing:
        # Update: accept name/tier changes; phone is immutable once set
        existing.name = data.get("name", existing.name)
        existing.tier = data.get("tier", existing.tier)
        existing.server_seq = await _next_seq(db)
        return

    # Check phone uniqueness
    phone_taken = (await db.execute(
        select(Customer).where(Customer.phone == data["phone"])
    )).scalar_one_or_none()

    if phone_taken:
        # Merge: update the existing customer with any new info instead of inserting
        phone_taken.name = data.get("name", phone_taken.name)
        phone_taken.server_seq = await _next_seq(db)
        return

    seq = await _next_seq(db)
    db.add(Customer(
        id=data["id"],
        name=data["name"],
        phone=data["phone"],
        tier=data.get("tier", 1),
        server_seq=seq,
    ))
    await db.flush()


async def _push_order_create(data: dict, device_id: str, db: AsyncSession) -> str:
    """
    Insert an offline-created order.  Returns the final pickup_code (may differ
    from the client's if there was a collision).
    """
    # Idempotent: if the server already has this ID, return its code
    existing = await db.get(Order, data["id"])
    if existing:
        return existing.pickup_code

    # Load customer for tier (needed for server-side pricing)
    customer = await db.get(Customer, data["customer_id"])
    if customer is None:
        raise ValueError(f"Customer {data['customer_id']!r} not found for offline order")

    # Recompute total_kobo — client value ignored
    line_inputs = [
        OrderLineInput(service_id=l["service_id"], piece_count=l["piece_count"])
        for l in data.get("lines", [])
    ]
    rules = await load_price_rules(
        [li.service_id for li in line_inputs], customer.tier, db
    )
    pricing = price_order(customer.tier, line_inputs, Turnaround(data["turnaround"]), rules)

    # Resolve pickup code — reassign if taken by a different order
    pickup_code = data.get("pickup_code", "") or _fresh_code()
    while True:
        conflict = (await db.execute(
            select(Order).where(Order.pickup_code == pickup_code)
        )).scalar_one_or_none()
        if conflict is None:
            break
        pickup_code = offline_pickup_code(data["branch_id"], device_id)

    seq = await _next_seq(db)
    order = Order(
        id=data["id"],
        branch_id=data["branch_id"],
        attendant_id=data.get("attendant_id"),
        customer_id=data["customer_id"],
        turnaround=Turnaround(data["turnaround"]),
        pickup_code=pickup_code,
        total_kobo=pricing.total_kobo,  # server-computed
        status=OrderStatus.received,
        version=1,
        server_seq=seq,
    )
    db.add(order)
    await db.flush()

    for priced in pricing.lines:
        db.add(OrderLine(
            order_id=order.id,
            service_id=priced.service_id,
            piece_count=priced.piece_count,
            unit_price_kobo=priced.unit_price_kobo,
            line_total_kobo=priced.line_total_kobo,
        ))
    await db.flush()

    return pickup_code


async def _push_order_update(data: dict, db: AsyncSession) -> None:
    """
    Apply a client-side order update.

    Only `status` is merged (furthest-along wins).  All money fields are
    ignored — the server never lets the client set total_kobo.
    """
    order = await db.get(Order, data["id"])
    if order is None:
        return  # order unknown to server yet; client should push a create first

    if "status" in data:
        client_status = OrderStatus(data["status"])
        merged = furthest_status(order.status, client_status)
        if merged != order.status:
            order.status = merged
            order.version += 1
            order.server_seq = await _next_seq(db)
            await db.flush()


async def _push_payment(data: dict, db: AsyncSession) -> None:
    """Append payment if not already present (idempotent by ID)."""
    existing = await db.get(Payment, data["id"])
    if existing:
        return  # already stored — never update

    seq = await _next_seq(db)
    db.add(Payment(
        id=data["id"],
        order_id=data["order_id"],
        amount_kobo=data["amount_kobo"],
        method=data["method"],
        server_seq=seq,
    ))
    await db.flush()


# ─────────────────────────────────────────────
# Push — public entry point
# ─────────────────────────────────────────────


@dataclass
class PushResult:
    reassigned_codes: dict[str, str]  # old_code → new_code
    server_seq: int


async def push(device_id: str, changes: dict, db: AsyncSession) -> PushResult:
    """
    Apply the client's offline changes.  Returns any pickup-code reassignments
    so the client can update its local records.
    """
    reassigned_codes: dict[str, str] = {}

    # 1. Customers first (may be referenced by orders)
    for c in changes.get("customers", {}).get("created", []):
        await _push_customer(c, db)
    for c in changes.get("customers", {}).get("updated", []):
        await _push_customer(c, db)

    # 2. Created orders — server recomputes total, resolves code conflicts
    for o in changes.get("orders", {}).get("created", []):
        original_code = o.get("pickup_code", "")
        final_code = await _push_order_create(o, device_id, db)
        if final_code != original_code:
            reassigned_codes[original_code] = final_code

    # 3. Order status merges — furthest-along wins
    for o in changes.get("orders", {}).get("updated", []):
        await _push_order_update(o, db)

    # 4. Payments — append-only, idempotent
    for p in changes.get("payments", {}).get("created", []):
        await _push_payment(p, db)

    server_seq = await _current_max_seq(db)
    return PushResult(reassigned_codes=reassigned_codes, server_seq=server_seq)
