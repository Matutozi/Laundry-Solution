from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import branch_guard, require_role
from app.models.order import Order
from app.models.order_line import OrderLine
from app.models.staff import Staff, StaffRole
from app.schemas.orders import OrderCreate, OrderLineResponse, OrderResponse
from app.services.orders import create_order as svc_create_order
from app.services.pricing import OrderLineInput, PriceRuleNotFound

router = APIRouter(prefix="/branches/{branch_id}", tags=["orders"])


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    branch_id: str,
    body: OrderCreate,
    staff: Staff = Depends(branch_guard),
    db: AsyncSession = Depends(get_session),
) -> OrderResponse:
    line_inputs = [
        OrderLineInput(service_id=line.service_id, piece_count=line.piece_count)
        for line in body.lines
    ]

    try:
        order, pricing = await svc_create_order(
            branch_id=branch_id,
            attendant_id=staff.id,
            customer_id=body.customer_id,
            turnaround=body.turnaround,
            line_inputs=line_inputs,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PriceRuleNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    result = await db.execute(
        select(OrderLine).where(OrderLine.order_id == order.id)
    )
    lines_db = result.scalars().all()

    return OrderResponse(
        id=order.id,
        branch_id=order.branch_id,
        customer_id=order.customer_id,
        attendant_id=order.attendant_id,
        status=order.status,
        turnaround=order.turnaround,
        pickup_code=order.pickup_code,
        total_kobo=order.total_kobo,
        version=order.version,
        lines=[
            OrderLineResponse(
                id=line.id,
                service_id=line.service_id,
                piece_count=line.piece_count,
                unit_price_kobo=line.unit_price_kobo,
                line_total_kobo=line.line_total_kobo,
            )
            for line in lines_db
        ],
    )


@router.get("/orders")
async def list_branch_orders(
    branch_id: str,
    _staff: Staff = Depends(branch_guard),
    db: AsyncSession = Depends(get_session),
) -> list[dict]:
    result = await db.execute(select(Order).where(Order.branch_id == branch_id))
    orders = result.scalars().all()
    return [{"id": o.id, "status": o.status, "pickup_code": o.pickup_code} for o in orders]


@router.get("/report")
async def branch_report(
    branch_id: str,
    _staff: Staff = Depends(require_role(StaffRole.manager, StaffRole.admin)),
) -> dict:
    """Manager/admin only — used for role-guard testing."""
    return {"branch_id": branch_id, "report": "ok"}
