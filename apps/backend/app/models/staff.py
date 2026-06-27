from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.order import Order
    from app.models.status_event import StatusEvent


class StaffRole(str, enum.Enum):
    attendant = "attendant"
    manager = "manager"
    admin = "admin"


class Staff(TimestampMixin, Base):
    __tablename__ = "staff"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    role: Mapped[StaffRole] = mapped_column(Enum(StaffRole), nullable=False)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    branch: Mapped[Branch] = relationship("Branch", back_populates="staff")
    orders: Mapped[list[Order]] = relationship("Order", back_populates="attendant")
    status_events: Mapped[list[StatusEvent]] = relationship("StatusEvent", back_populates="staff")
