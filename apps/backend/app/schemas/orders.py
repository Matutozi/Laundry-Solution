from pydantic import BaseModel, Field

from app.models.order import OrderStatus, Turnaround


class OrderLineCreate(BaseModel):
    service_id: str
    piece_count: int = Field(ge=1)


class OrderCreate(BaseModel):
    customer_id: str
    turnaround: Turnaround
    lines: list[OrderLineCreate] = Field(min_length=1)


class OrderLineResponse(BaseModel):
    id: str
    service_id: str
    piece_count: int
    unit_price_kobo: int
    line_total_kobo: int


class OrderResponse(BaseModel):
    id: str
    branch_id: str
    customer_id: str
    attendant_id: str
    status: OrderStatus
    turnaround: Turnaround
    pickup_code: str
    total_kobo: int
    version: int
    lines: list[OrderLineResponse]
