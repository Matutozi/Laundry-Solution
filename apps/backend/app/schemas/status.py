from pydantic import BaseModel

from app.models.order import OrderStatus


class StatusTransitionRequest(BaseModel):
    to_status: OrderStatus


class StatusTransitionResponse(BaseModel):
    order_id: str
    from_status: OrderStatus
    to_status: OrderStatus
    version: int
