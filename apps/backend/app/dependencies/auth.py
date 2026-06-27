from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.staff import Staff, StaffRole
from app.services.auth import decode_access_token

bearer = HTTPBearer()


async def get_current_staff(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_session),
) -> Staff:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    staff_id: str = payload.get("sub")
    result = await db.execute(select(Staff).where(Staff.id == staff_id))
    staff = result.scalar_one_or_none()
    if staff is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Staff not found")
    return staff


def require_role(*roles: StaffRole):
    """Dependency factory — checks that current staff has one of the given roles."""
    async def _check(staff: Staff = Depends(get_current_staff)) -> Staff:
        if staff.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {[r.value for r in roles]}",
            )
        return staff
    return _check


async def branch_guard(
    branch_id: str,
    staff: Staff = Depends(get_current_staff),
) -> Staff:
    """Attendants may only access their own branch. Managers and admins are unrestricted."""
    if staff.role == StaffRole.attendant and staff.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Attendants can only access their own branch",
        )
    return staff
