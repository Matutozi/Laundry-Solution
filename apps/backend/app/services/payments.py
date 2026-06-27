from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.payment import Payment, PaymentMethod


async def add_payment(
    order_id: str,
    amount_kobo: int,
    method: PaymentMethod,
    db: AsyncSession,
) -> tuple[Payment, int]:
    """
    Append a payment row (never update existing ones).

    Returns (payment, outstanding_kobo).
    outstanding_kobo may be negative if the order is overpaid.
    Raises ValueError if the order is not found or amount < 1.
    """
    if amount_kobo < 1:
        raise ValueError("Payment amount must be at least 1 kobo")

    order = await db.get(Order, order_id)
    if order is None:
        raise ValueError(f"Order '{order_id}' not found")

    payment = Payment(order_id=order_id, amount_kobo=amount_kobo, method=method)
    db.add(payment)
    await db.flush()

    # Recompute total paid (includes the just-inserted row)
    result = await db.execute(
        select(func.sum(Payment.amount_kobo)).where(Payment.order_id == order_id)
    )
    total_paid: int = result.scalar() or 0
    outstanding = order.total_kobo - total_paid

    return payment, outstanding
