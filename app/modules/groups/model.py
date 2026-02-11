"""
Group and GroupMember models.
"""
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import String, Boolean, ForeignKey, DateTime, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.common.mixins import UUIDMixin, TimestampMixin, SoftDeleteMixin
from app.common.enums import GroupMemberRole

if TYPE_CHECKING:
    from app.modules.tenants.model import Tenant
    from app.modules.users.model import User


class Group(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):

    __tablename__ = "groups"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        backref="groups",
        lazy="selectin"
    )
    
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="selectin"
    )
    
    members: Mapped[list["GroupMember"]] = relationship(
        "GroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # Constraints and Indexes
    __table_args__ = (
        Index(
            "idx_unique_active_group_name_per_tenant", 
            "tenant_id", 
            "name", 
            unique=True,
            postgresql_where=(SoftDeleteMixin.deleted_at == None)
        ),
    )

    def __repr__(self) -> str:
        return f"<Group(id={self.id}, name={self.name}, tenant_id={self.tenant_id})>"


class GroupMember(Base, UUIDMixin, TimestampMixin):
    """
    Junction table representing group membership and roles.
    Note: joined_at is tracked by created_at from TimestampMixin.
    """
    __tablename__ = "group_members"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    role: Mapped[GroupMemberRole] = mapped_column(
        SQLEnum(GroupMemberRole, name="group_member_role", create_type=True),
        nullable=False,
        default=GroupMemberRole.MEMBER
    )
    
    left_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None
    )

    # Relationships
    group: Mapped["Group"] = relationship(
        "Group",
        back_populates="members",
        lazy="selectin"
    )
    
    user: Mapped["User"] = relationship(
        "User",
        backref="group_memberships",
        lazy="selectin"
    )

    # Constraints and Indexes
    __table_args__ = (
        Index("idx_unique_active_member", "group_id", "user_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<GroupMember(group_id={self.group_id}, user_id={self.user_id}, role={self.role})>"

    @property
    def user_email(self) -> str:
        return self.user.email

    @property
    def user_name(self) -> str:
        return self.user.full_name
