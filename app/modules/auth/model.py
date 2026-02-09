"""
Token blacklist model for JWT revocation.
"""
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid as uuid_pkg

from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.common.mixins import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.modules.users.model import User


class TokenBlacklist(Base, UUIDMixin, TimestampMixin):
    """Token blacklist for revoked JWT tokens."""
    
    __tablename__ = "token_blacklist"
    
    jti: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        comment="JWT ID - unique identifier for the token"
    )
    
    user_id: Mapped[uuid_pkg.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    token_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Type of token: access or refresh"
    )
    
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When the token expires (from JWT exp claim)"
    )
    
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="When the token was revoked"
    )
    
    reason: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Reason for revocation (e.g., 'logout', 'admin_revoke')"
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="blacklisted_tokens")
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_jti_lookup", "jti"),
        Index("idx_user_tokens", "user_id", "token_type"),
        Index("idx_expires_at", "expires_at"),
    )
    
    def __repr__(self) -> str:
        return f"<TokenBlacklist(jti={self.jti}, user_id={self.user_id}, type={self.token_type})>"
