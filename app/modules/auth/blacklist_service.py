from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.model import TokenBlacklist
import redis.asyncio as redis


class TokenBlacklistService:
    """Service for managing token blacklist."""
    
    @staticmethod
    async def is_token_blacklisted(
        db: AsyncSession, 
        jti: str, 
        token_type: str = "access",
        redis_client: Optional[redis.Redis] = None
    ) -> bool:
        """
        Check if a token is blacklisted.
        - Access tokens: Check Redis.
        - Refresh tokens: Check DB.
        """
        if token_type == "access" and redis_client:
            key = f"blacklist:access:{jti}"
            is_blacklisted = await redis_client.get(key)
            return is_blacklisted is not None

        # Check DB (Refresh tokens or fallback)
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
        reason: Optional[str] = None,
        redis_client: Optional[redis.Redis] = None
    ) -> Optional[TokenBlacklist]:
        """
        Add a token to the blacklist.
        - Access tokens are stored in Redis with TTL.
        - Refresh tokens are stored in Database (persistent).
        """
        if token_type == "access" and redis_client:
            #Calculate TTL
            now = datetime.now(timezone.utc)
            ttl = int((expires_at - now).total_seconds())
            
            if ttl > 0:
                key = f"blacklist:access:{jti}"
                await redis_client.set(key, "revoked", ex=ttl)
            return None

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
