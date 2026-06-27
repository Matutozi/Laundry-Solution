"""Pickup-by-code endpoints — used at the counter when a customer collects their laundry."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import get_current_staff
from app.models.order import Order, OrderStatus
from app.models.order_line import OrderLine
from app.models.payment import Payment
from app.models.staff import Staff
from app.schemas.orders import OrderLineResponse, OrderResponse
from app.services.status import InvalidTransitionError, apply_status_transition

router = APIRouter(prefix="/pickup", tags=["pickup"])


async def _order_by_code(code: str, db: AsyncSession) -> Order:
    result = await db.execute(select(Order).where(Order.pickup_code == code))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No order with pickup code '{code}'")
    return order


@router.get("/{code}")
async def lookup_by_code(
    code: str,
    _staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_session),
) -> dict:
    order = await _order_by_code(code, db)
    lines = (await db.execute(select(OrderLine).where(OrderLine.order_id == order.id))).scalars().all()
    total_paid: int = int((await db.execute(
        select(func.coalesce(func.sum(Payment.amount_kobo), 0)).where(Payment.order_id == order.id)
    )).scalar() or 0)

    return {
        "id": order.id,
        "pickup_code": order.pickup_code,
        "status": order.status,
        "turnaround": order.turnaround,
        "total_kobo": order.total_kobo,
        "paid_kobo": total_paid,
        "outstanding_kobo": order.total_kobo - total_paid,
        "version": order.version,
        "lines": [
            OrderLineResponse(id=l.id, service_id=l.service_id, piece_count=l.piece_count,
                              unit_price_kobo=l.unit_price_kobo, line_total_kobo=l.line_total_kobo)
            for l in lines
        ],
    }


@router.post("/{code}/release")
async def release_by_code(
    code: str,
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Mark a ready order as picked_up. Returns the updated status and version."""
    order = await _order_by_code(code, db)
    try:
        order, event = await apply_status_transition(
            order.id, OrderStatus.picked_up, staff.id, db
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return {"order_id": order.id, "status": order.status, "version": order.version}
