"""Per-order endpoints: payments, status transitions, detail fetch."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import get_current_staff
from app.dependencies.queue import get_task_queue
from app.models.order import Order, OrderStatus
from app.models.order_line import OrderLine
from app.models.staff import Staff, StaffRole
from app.queue import ArqTaskQueue, MemoryTaskQueue
from app.schemas.orders import OrderLineResponse, OrderResponse
from app.schemas.payments import PaymentCreate, PaymentResponse
from app.schemas.status import StatusTransitionRequest, StatusTransitionResponse
from app.services.payments import add_payment
from app.services.status import InvalidTransitionError, apply_status_transition

router = APIRouter(prefix="/orders", tags=["orders"])


async def _load_order_guarded(order_id: str, staff: Staff, db: AsyncSession) -> Order:
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if staff.role == StaffRole.attendant and order.branch_id != staff.branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return order


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_session),
) -> OrderResponse:
    order = await _load_order_guarded(order_id, staff, db)
    lines = (await db.execute(select(OrderLine).where(OrderLine.order_id == order.id))).scalars().all()
    return OrderResponse(
        id=order.id, branch_id=order.branch_id, customer_id=order.customer_id,
        attendant_id=order.attendant_id, status=order.status, turnaround=order.turnaround,
        pickup_code=order.pickup_code, total_kobo=order.total_kobo, version=order.version,
        lines=[OrderLineResponse(id=l.id, service_id=l.service_id, piece_count=l.piece_count,
                                  unit_price_kobo=l.unit_price_kobo, line_total_kobo=l.line_total_kobo)
               for l in lines],
    )


@router.post("/{order_id}/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    order_id: str,
    body: PaymentCreate,
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_session),
    queue: ArqTaskQueue | MemoryTaskQueue = Depends(get_task_queue),
) -> PaymentResponse:
    await _load_order_guarded(order_id, staff, db)
    try:
        payment, outstanding = await add_payment(order_id, body.amount_kobo, body.method, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await queue.enqueue("send_receipt", order_id=order_id, event="paid")
    return PaymentResponse(
        id=payment.id, order_id=payment.order_id, amount_kobo=payment.amount_kobo,
        method=payment.method, recorded_at=payment.recorded_at, outstanding_kobo=outstanding,
    )


@router.post("/{order_id}/status", response_model=StatusTransitionResponse)
async def transition_status(
    order_id: str,
    body: StatusTransitionRequest,
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_session),
    queue: ArqTaskQueue | MemoryTaskQueue = Depends(get_task_queue),
) -> StatusTransitionResponse:
    await _load_order_guarded(order_id, staff, db)
    try:
        order, event = await apply_status_transition(order_id, body.to_status, staff.id, db)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if order.status == OrderStatus.ready:
        await queue.enqueue("send_receipt", order_id=order.id, event="ready")
    return StatusTransitionResponse(
        order_id=order.id, from_status=event.from_status,
        to_status=event.to_status, version=order.version,
    )
