"""
Travel Event model.
"""
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import String, ForeignKey, DateTime, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.common.mixins import UUIDMixin, TimestampMixin, SoftDeleteMixin
from app.common.enums import EventStatus

if TYPE_CHECKING:
    from app.modules.tenants.model import Tenant
    from app.modules.users.model import User
    from app.modules.groups.model import Group


class TravelEvent(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    Travel Event model.
    Represents a travel event within a group.
    """

    __tablename__ = "travel_events"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    destination: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EventStatus.PLANNED.value,
        server_default=EventStatus.PLANNED.value
    )

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="events")
    group: Mapped["Group"] = relationship("Group", back_populates="events")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])

    # Table constraints
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="valid_time_range"),
        Index("idx_events_group", "group_id"),
        Index("idx_events_tenant", "tenant_id"),
        Index("idx_events_deleted", "deleted_at"),
        Index("idx_events_start_time", "start_time"),
        Index(
            "idx_unique_event_name_per_group",
            "group_id",
            "name",
            unique=True,
            postgresql_where="deleted_at IS NULL"
        ),
    )

    @property
    def creator_name(self) -> Optional[str]:
        """Get creator's full name."""
        return self.creator.full_name if self.creator else None

    def __repr__(self) -> str:
        return f"<TravelEvent(id={self.id}, name={self.name}, destination={self.destination})>"
