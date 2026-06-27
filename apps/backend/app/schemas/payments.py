from datetime import datetime

from pydantic import BaseModel, Field

from app.models.payment import PaymentMethod


class PaymentCreate(BaseModel):
    amount_kobo: int = Field(ge=1)
    method: PaymentMethod


class PaymentResponse(BaseModel):
    id: str
    order_id: str
    amount_kobo: int
    method: PaymentMethod
    recorded_at: datetime
    outstanding_kobo: int
