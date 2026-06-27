from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.branch import Branch

from app.database import Base


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    branches: Mapped[list[Branch]] = relationship("Branch", back_populates="organization")
