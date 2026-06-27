from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.order import Order


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (CheckConstraint("tier BETWEEN 1 AND 3", name="ck_customer_tier"),)

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    server_seq: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    orders: Mapped[list[Order]] = relationship("Order", back_populates="customer")
