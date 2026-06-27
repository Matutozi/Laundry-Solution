from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import uuid_pk
from app.models.order import OrderStatus

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.staff import Staff


class StatusEvent(Base):
    """Server-stamped, append-only event log for order status transitions."""

    __tablename__ = "status_events"

    id: Mapped[str] = uuid_pk()
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False)
    staff_id: Mapped[str] = mapped_column(ForeignKey("staff.id"), nullable=False)
    from_status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), nullable=False)
    to_status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), nullable=False)
    server_timestamp: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order: Mapped[Order] = relationship("Order", back_populates="status_events")
    staff: Mapped[Staff] = relationship("Staff", back_populates="status_events")
