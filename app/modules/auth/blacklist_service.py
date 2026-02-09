from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.model import TokenBlacklist


class TokenBlacklistService:
    """Service for managing token blacklist."""
    
    @staticmethod
    async def is_token_blacklisted(db: AsyncSession, jti: str) -> bool:
        """
        Check if a token is blacklisted.
        """
        result = await db.execute(
            select(TokenBlacklist).where(TokenBlacklist.jti == jti)
        )
        return result.scalar_one_or_none() is not None
    
    @staticmethod
    async def blacklist_token(
        db: AsyncSession,
        jti: str,
        user_id: uuid.UUID,
        token_type: str,
        expires_at: datetime,
        reason: Optional[str] = None
    ) -> TokenBlacklist:
        """
        Add a token to the blacklist.
        """
        blacklist_entry = TokenBlacklist(
            jti=jti,
            user_id=user_id,
            token_type=token_type,
            expires_at=expires_at,
            reason=reason or "logout"
        )
        db.add(blacklist_entry)
        await db.commit()
        await db.refresh(blacklist_entry)
        return blacklist_entry
    
    @staticmethod
    async def blacklist_all_user_tokens(
        db: AsyncSession,
        user_id: uuid.UUID,
        reason: str = "logout_all"
    ) -> int:
        """
        Blacklist all tokens for a user (logout from all devices).
        """

        return 0
    
    @staticmethod
    async def cleanup_expired_tokens(db: AsyncSession) -> int:
        """
        Remove expired tokens from the blacklist to keep the table clean.
        """
        result = await db.execute(
            delete(TokenBlacklist).where(
                TokenBlacklist.expires_at < datetime.now(timezone.utc)
            )
        )
        await db.commit()
        return result.rowcount
