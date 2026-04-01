"""
Live Location model.
"""
from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, ForeignKey, Float, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.common.mixins import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.modules.tenants.model import Tenant
    from app.modules.users.model import User
    from app.modules.events.model import TravelEvent


class LiveLocation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "live_locations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("travel_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="selectin")
    event: Mapped["TravelEvent"] = relationship("TravelEvent", lazy="selectin")
    user: Mapped["User"] = relationship("User", lazy="selectin")

    # Constraints
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_live_location_event_user"),
    )

    def __repr__(self) -> str:
        return f"<LiveLocation(event_id={self.event_id}, user_id={self.user_id}, lat={self.latitude}, lng={self.longitude})>"
