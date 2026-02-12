"""
GroupMessage model for storing chat history.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import String, Text, ForeignKey, ForeignKeyConstraint, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.common.mixins import UUIDMixin, TimestampMixin
from app.common.enums import MessageType

if TYPE_CHECKING:
    from app.modules.tenants.model import Tenant
    from app.modules.groups.model import Group
    from app.modules.users.model import User


class GroupMessage(Base, UUIDMixin, TimestampMixin):
    """
    Stores messages sent within a group.
    """
    __tablename__ = "group_messages"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    message_type: Mapped[MessageType] = mapped_column(
        SQLEnum(MessageType, name="messagetype", create_type=True),
        nullable=False,
        default=MessageType.TEXT
    )
    
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="selectin")
    group: Mapped["Group"] = relationship("Group", lazy="selectin")
    sender: Mapped[Optional["User"]] = relationship("User", lazy="selectin")

    @property
    def sender_name(self) -> Optional[str]:
        return self.sender.full_name if self.sender else "System"

    def __repr__(self) -> str:
        return f"<GroupMessage(id={self.id}, group_id={self.group_id}, sender_id={self.sender_id})>"
