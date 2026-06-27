"""Receipt job: build and dispatch order receipts via WhatsApp + SMS.

Two events trigger this job:
  "paid"  — a payment was recorded on the order
  "ready" — the order status was moved to `ready`

The job function accepts either:
  ctx["db_session"] — an existing AsyncSession (used in tests to share the
                      test transaction so uncommitted data is visible)
  ctx["db_engine"]  — an AsyncEngine (used in production; creates its own session)
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.customer import Customer
from app.models.order import Order
from app.models.order_line import OrderLine
from app.models.payment import Payment
from app.models.service import Service
from app.models.staff import Staff
from app.notifications.base import NotificationProvider


# ---------------------------------------------------------------------------
# Pure receipt data types and builder
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReceiptLine:
    service_name: str
    piece_count: int
    line_total_kobo: int


@dataclass(frozen=True)
class Receipt:
    pickup_code: str
    customer_name: str
    customer_phone: str
    staff_name: str
    lines: tuple[ReceiptLine, ...]
    total_kobo: int
    paid_kobo: int
    outstanding_kobo: int
    event: str  # "paid" | "ready"


def _naira(kobo: int) -> str:
    return f"₦{kobo / 100:,.2f}"


def build_receipt_text(r: Receipt) -> str:
    heading = "Wise-Wash — Order Ready!" if r.event == "ready" else "Wise-Wash Payment Receipt"
    parts = [
        "═" * 30,
        f"  {heading}",
        "═" * 30,
        f"Pickup code: {r.pickup_code}",
        "",
    ]
    for line in r.lines:
        label = f"{line.service_name} \xd7 {line.piece_count}"
        parts.append(f"{label:<22} {_naira(line.line_total_kobo):>10}")
    parts += [
        "─" * 30,
        f"{'Total:':<22} {_naira(r.total_kobo):>10}",
        f"{'Paid:':<22} {_naira(r.paid_kobo):>10}",
        f"{'Balance:':<22} {_naira(r.outstanding_kobo):>10}",
        "─" * 30,
        f"Attended by: {r.staff_name}",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# arq job function
# ---------------------------------------------------------------------------


async def send_receipt(ctx: dict, *, order_id: str, event: str) -> None:
    """arq job — called by the worker for every order-paid and order-ready event."""
    provider: NotificationProvider = ctx["notification_provider"]

    if "db_session" in ctx:
        # Test path: reuse the caller's session so uncommitted rows are visible
        db: AsyncSession = ctx["db_session"]
        receipt = await _build_receipt(db, order_id, event)
    else:
        session_factory = async_sessionmaker(ctx["db_engine"], expire_on_commit=False)
        async with session_factory() as db:
            receipt = await _build_receipt(db, order_id, event)

    if receipt is None:
        return  # order deleted between enqueue and execution — skip silently

    text = build_receipt_text(receipt)
    await provider.send_whatsapp(receipt.customer_phone, text)
    await provider.send_sms(receipt.customer_phone, text)


async def _build_receipt(db: AsyncSession, order_id: str, event: str) -> Receipt | None:
    order = await db.get(Order, order_id)
    if order is None:
        return None

    customer = await db.get(Customer, order.customer_id)
    staff = await db.get(Staff, order.attendant_id)

    rows = (await db.execute(
        select(OrderLine, Service)
        .join(Service, OrderLine.service_id == Service.id)
        .where(OrderLine.order_id == order_id)
    )).all()

    paid_kobo: int = int((await db.execute(
        select(func.coalesce(func.sum(Payment.amount_kobo), 0))
        .where(Payment.order_id == order_id)
    )).scalar() or 0)

    return Receipt(
        pickup_code=order.pickup_code,
        customer_name=customer.name,
        customer_phone=customer.phone,
        staff_name=staff.name,
        lines=tuple(
            ReceiptLine(
                service_name=svc.name,
                piece_count=line.piece_count,
                line_total_kobo=line.line_total_kobo,
            )
            for line, svc in rows
        ),
        total_kobo=order.total_kobo,
        paid_kobo=paid_kobo,
        outstanding_kobo=order.total_kobo - paid_kobo,
        event=event,
    )
