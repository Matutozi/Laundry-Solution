from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PinAuthRequest(BaseModel):
    staff_id: str
    pin: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
