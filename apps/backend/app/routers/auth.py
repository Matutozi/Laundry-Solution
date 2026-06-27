from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models.staff import Staff
from app.schemas.auth import LoginRequest, PinAuthRequest, TokenResponse
from app.services.auth import (
    create_access_token,
    verify_password,
    verify_pin,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_session)) -> TokenResponse:
    result = await db.execute(select(Staff).where(Staff.email == body.email))
    staff = result.scalar_one_or_none()

    if staff is None or not staff.password_hash or not verify_password(body.password, staff.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(
        staff_id=staff.id,
        role=staff.role.value,
        branch_id=staff.branch_id,
    )
    return TokenResponse(access_token=token)


@router.post("/pin", response_model=TokenResponse)
async def pin_auth(body: PinAuthRequest, db: AsyncSession = Depends(get_session)) -> TokenResponse:
    """Short-lived token for switching staff on a shared tablet."""
    result = await db.execute(select(Staff).where(Staff.id == body.staff_id))
    staff = result.scalar_one_or_none()

    if staff is None or not staff.pin_hash or not verify_pin(body.pin, staff.pin_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PIN")

    token = create_access_token(
        staff_id=staff.id,
        role=staff.role.value,
        branch_id=staff.branch_id,
        expires_minutes=settings.pin_token_expire_minutes,
    )
    return TokenResponse(access_token=token)
