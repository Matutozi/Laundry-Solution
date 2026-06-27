from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.order_line import OrderLine
    from app.models.price_rule import PriceRule


class Service(TimestampMixin, Base):
    __tablename__ = "services"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    price_rules: Mapped[list[PriceRule]] = relationship("PriceRule", back_populates="service")
    order_lines: Mapped[list[OrderLine]] = relationship("OrderLine", back_populates="service")
