from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import uuid_pk

if TYPE_CHECKING:
    from app.models.order import Order


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    transfer = "transfer"
    pos = "pos"


class Payment(Base):
    """Append-only. Never update or delete rows."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_kobo > 0", name="ck_payment_amount_positive"),
    )

    id: Mapped[str] = uuid_pk()
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False)
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), nullable=False)
    recorded_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    server_seq: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    order: Mapped[Order] = relationship("Order", back_populates="payments")
