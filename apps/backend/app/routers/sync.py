"""WatermelonDB sync endpoints — pull and push."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import get_current_staff
from app.models.staff import Staff
from app.schemas.sync import PullResponse, PushRequest, PushResponse
from app.services.sync import pull, push

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/pull", response_model=PullResponse)
async def sync_pull(
    since: int = Query(default=0, ge=0, description="Last server_seq the client knows about"),
    _staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_session),
) -> PullResponse:
    result = await pull(since, db)
    return PullResponse(
        changes={
            "orders": result.orders,
            "payments": result.payments,
            "customers": result.customers,
        },
        server_seq=result.server_seq,
    )


@router.post("/push", response_model=PushResponse)
async def sync_push(
    body: PushRequest,
    _staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_session),
) -> PushResponse:
    result = await push(body.device_id, body.changes, db)
    return PushResponse(
        reassigned_codes=result.reassigned_codes,
        server_seq=result.server_seq,
    )
