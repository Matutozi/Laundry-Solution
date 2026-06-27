from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.organization import Organization
    from app.models.staff import Staff


class Branch(TimestampMixin, Base):
    __tablename__ = "branches"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)

    organization: Mapped[Organization] = relationship("Organization", back_populates="branches")
    staff: Mapped[list[Staff]] = relationship("Staff", back_populates="branch")
    orders: Mapped[list[Order]] = relationship("Order", back_populates="branch")
