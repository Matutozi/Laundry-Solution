from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.customer import Customer
    from app.models.order_line import OrderLine
    from app.models.payment import Payment
    from app.models.staff import Staff
    from app.models.status_event import StatusEvent


class OrderStatus(str, enum.Enum):
    received = "received"
    processing = "processing"
    ready = "ready"
    picked_up = "picked_up"
    delivered = "delivered"
    cancelled = "cancelled"


class Turnaround(str, enum.Enum):
    regular = "regular"    # 1×
    express = "express"    # 1.5×
    same_day = "same_day"  # 3×


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total_kobo >= 0", name="ck_order_total_kobo_non_negative"),
    )

    id: Mapped[str] = uuid_pk()
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False)
    attendant_id: Mapped[str] = mapped_column(ForeignKey("staff.id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), nullable=False, default=OrderStatus.received
    )
    turnaround: Mapped[Turnaround] = mapped_column(
        Enum(Turnaround), nullable=False, default=Turnaround.regular
    )
    pickup_code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    total_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    server_seq: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    branch: Mapped[Branch] = relationship("Branch", back_populates="orders")
    attendant: Mapped[Staff] = relationship("Staff", back_populates="orders")
    customer: Mapped[Customer] = relationship("Customer", back_populates="orders")
    lines: Mapped[list[OrderLine]] = relationship(
        "OrderLine", back_populates="order", cascade="all, delete-orphan"
    )
    payments: Mapped[list[Payment]] = relationship("Payment", back_populates="order")
    status_events: Mapped[list[StatusEvent]] = relationship(
        "StatusEvent", back_populates="order", cascade="all, delete-orphan"
    )
