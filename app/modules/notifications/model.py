"""
Notification model.
"""
from typing import Optional
import uuid
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.common.mixins import UUIDMixin, TimestampMixin, SoftDeleteMixin

class Notification(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "notifications"

    # Fields
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("tenants.id"), 
        nullable=False,
        index=True
    )
    receiver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id"), 
        nullable=False,
        index=True
    )
    
    type: Mapped[str] = mapped_column(String, nullable=False)
    
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    
    reference_type: Mapped[str] = mapped_column(String, nullable=False)
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), 
        nullable=True
    )

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    receiver = relationship("User", back_populates="notifications")
