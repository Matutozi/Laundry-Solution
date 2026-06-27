from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=7, max_length=20)
    tier: int = Field(default=1, ge=1, le=3)


class CustomerResponse(BaseModel):
    id: str
    name: str
    phone: str
    tier: int
