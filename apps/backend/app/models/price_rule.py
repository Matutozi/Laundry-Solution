from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.service import Service


class PriceRule(TimestampMixin, Base):
    __tablename__ = "price_rules"
    __table_args__ = (
        UniqueConstraint("service_id", "tier", name="uq_price_rule_service_tier"),
        CheckConstraint("tier BETWEEN 1 AND 3", name="ck_price_rule_tier"),
        CheckConstraint("price_kobo >= 0", name="ck_price_rule_price_positive"),
    )

    id: Mapped[str] = uuid_pk()
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    price_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)

    service: Mapped[Service] = relationship("Service", back_populates="price_rules")
