from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import String, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.common.mixins import UUIDMixin, TimestampMixin, SoftDeleteMixin
from app.common.enums import UserRole

if TYPE_CHECKING:
    from app.modules.tenants.model import Tenant
    from app.modules.tenants.model import Tenant


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    
    __tablename__ = "users"
    
    # Fields
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,  # Nullable for SUPER_ADMIN
        index=True
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    first_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    last_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role", create_type=True),
        nullable=False,
        default=UserRole.USER
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,  
        nullable=False
    )
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,  # Set to True on email verification
        nullable=False
    )
    
    # Relationships
    tenant: Mapped[Optional["Tenant"]] = relationship(
        "Tenant",
        back_populates="users",
        lazy="selectin"
    )
    
    blacklisted_tokens = relationship(
        "TokenBlacklist",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    notifications = relationship(
        "Notification",
        back_populates="receiver",
        cascade="all, delete-orphan",
        lazy="select"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
    
    @property
    def full_name(self) -> str:
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def tenant_name(self) -> Optional[str]:
        """Get tenant name if tenant exists."""
        return self.tenant.name if self.tenant else None
