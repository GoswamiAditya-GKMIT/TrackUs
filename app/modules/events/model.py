"""
Travel Event model.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import String, ForeignKey, DateTime, CheckConstraint, Index, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.common.mixins import UUIDMixin, TimestampMixin, SoftDeleteMixin
from app.common.enums import EventStatus, ParticipantStatus

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

    status: Mapped[EventStatus] = mapped_column(
        SQLEnum(EventStatus, name="event_status", create_type=True),
        nullable=False,
        default=EventStatus.PLANNED
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
    participants: Mapped[list["EventParticipant"]] = relationship(
        "EventParticipant",
        back_populates="event",
        cascade="all, delete-orphan"
    )

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

    @property
    def participant_count(self) -> int:
        """Count of accepted participants."""
        if 'participants' not in self.__dict__:
            return 0
        return sum(1 for p in self.participants if p.status == ParticipantStatus.ACCEPTED)

    def __repr__(self) -> str:
        return f"<TravelEvent(id={self.id}, name={self.name}, destination={self.destination})>"


class EventParticipant(Base, UUIDMixin, TimestampMixin):

    __tablename__ = "event_participants"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("travel_events.id", ondelete="CASCADE"),
        nullable=False
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    status: Mapped[ParticipantStatus] = mapped_column(
        SQLEnum(ParticipantStatus, name="participant_status", create_type=True),
        nullable=False,
        default=ParticipantStatus.INVITED
    )

    responded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    event: Mapped["TravelEvent"] = relationship("TravelEvent", back_populates="participants")
    user: Mapped["User"] = relationship("User")

    # Table constraints
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="unique_event_participant"),
    )

    @property
    def user_name(self) -> Optional[str]:
        """Get participant's full name."""
        return self.user.full_name if self.user else None

    @property
    def user_email(self) -> Optional[str]:
        """Get participant's email."""
        return self.user.email if self.user else None

    def __repr__(self) -> str:
        return f"<EventParticipant(id={self.id}, event_id={self.event_id}, user_id={self.user_id}, status={self.status})>"
