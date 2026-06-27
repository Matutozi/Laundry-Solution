from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(pin: str, hashed: str) -> bool:
    return bcrypt.checkpw(pin.encode(), hashed.encode())


def create_access_token(staff_id: str, role: str, branch_id: str, expires_minutes: int | None = None) -> str:
    expires = expires_minutes or settings.access_token_expire_minutes
    payload = {
        "sub": staff_id,
        "role": role,
        "branch_id": branch_id,
        "exp": datetime.now(UTC) + timedelta(minutes=expires),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
