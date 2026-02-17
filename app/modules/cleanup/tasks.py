import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.modules.auth.model import TokenBlacklist
from app.modules.users.model import User
from app.core.config import settings

logger = logging.getLogger(__name__)

async def _cleanup_expired_tokens(session: AsyncSession):
    """Delete expired tokens from blacklist."""
    stmt = delete(TokenBlacklist).where(TokenBlacklist.expires_at < datetime.now(timezone.utc))
    result = await session.execute(stmt)
    await session.commit()
    logger.info(f"Cleaned up {result.rowcount} expired blacklisted tokens")

async def _cleanup_unverified_users(session: AsyncSession):
    """Delete users who haven't verified email after 48 hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    stmt = delete(User).where(
        and_(
            User.is_email_verified == False,
            User.created_at < cutoff
        )
    )
    result = await session.execute(stmt)
    await session.commit()
    logger.info(f"Cleaned up {result.rowcount} unverified users (older than 48h)")

async def _cleanup_soft_deleted_users(session: AsyncSession):
    """Permanently delete users soft-deleted more than 7 days ago."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    
    stmt = delete(User).where(
        and_(
            User.deleted_at.is_not(None),
            User.deleted_at < cutoff
        )
    )
    result = await session.execute(stmt)
    await session.commit()
    logger.info(f"Permanently deleted {result.rowcount} soft-deleted users (older than 7 days)")

@celery_app.task
def cleanup_expired_tokens():
    """Celery task wrapper for expired token cleanup."""
    async def run():
        async with AsyncSessionLocal() as session:
            await _cleanup_expired_tokens(session)
    
    asyncio.run(run())

@celery_app.task
def cleanup_unverified_users():
    """Celery task wrapper for unverified user cleanup."""
    async def run():
        async with AsyncSessionLocal() as session:
            await _cleanup_unverified_users(session)
            
    asyncio.run(run())

@celery_app.task
def cleanup_soft_deleted_users():
    """Celery task wrapper for soft-deleted user cleanup."""
    async def run():
        async with AsyncSessionLocal() as session:
            await _cleanup_soft_deleted_users(session)
            
    asyncio.run(run())
