from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import uuid_pk

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.service import Service


class OrderLine(Base):
    __tablename__ = "order_lines"
    __table_args__ = (
        CheckConstraint("piece_count > 0", name="ck_order_line_piece_count_positive"),
        CheckConstraint("unit_price_kobo >= 0", name="ck_order_line_unit_price_non_negative"),
        CheckConstraint("line_total_kobo >= 0", name="ck_order_line_total_non_negative"),
    )

    id: Mapped[str] = uuid_pk()
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), nullable=False)
    piece_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_total_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)

    order: Mapped[Order] = relationship("Order", back_populates="lines")
    service: Mapped[Service] = relationship("Service", back_populates="order_lines")
