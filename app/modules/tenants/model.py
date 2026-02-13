from typing import TYPE_CHECKING

from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.common.mixins import UUIDMixin, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.modules.users.model import User
    from app.modules.events.model import TravelEvent


class Tenant(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Tenant model representing an organization in the platform."""
    
    __tablename__ = "tenants"
    
    # Fields
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    
    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="tenant",
        lazy="selectin"
    )
    
    events: Mapped[list["TravelEvent"]] = relationship(
        "TravelEvent",
        back_populates="tenant",
        lazy="select"
    )
    
    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, name={self.name})>"
