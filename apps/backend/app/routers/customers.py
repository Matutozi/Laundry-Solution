from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import get_current_staff
from app.models.staff import Staff
from app.schemas.customers import CustomerCreate, CustomerResponse
from app.services.customers import create_customer, search_customers

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create(
    body: CustomerCreate,
    _staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_session),
) -> CustomerResponse:
    try:
        customer = await create_customer(body.name, body.phone, body.tier, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return CustomerResponse(id=customer.id, name=customer.name, phone=customer.phone, tier=customer.tier)


@router.get("", response_model=list[CustomerResponse])
async def search(
    q: str = Query(min_length=1),
    _staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_session),
) -> list[CustomerResponse]:
    customers = await search_customers(q, db)
    return [CustomerResponse(id=c.id, name=c.name, phone=c.phone, tier=c.tier) for c in customers]
