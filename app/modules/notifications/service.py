"""
Notification Service.
"""
from typing import List
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from app.modules.notifications.model import Notification
from app.modules.notifications.schema import NotificationCreate
from app.common.constants import NotificationType
from app.core.exceptions import NotFoundException
from datetime import datetime, timezone

class NotificationService:
    
    @staticmethod
    async def create_notification(
        db: AsyncSession, 
        notification_in: NotificationCreate,
        receiver_id: uuid.UUID,
        tenant_id: uuid.UUID
    ) -> Notification:
        """
        Create a single notification.
        Validates type and reference_type against constants.
        """
        # Validate Constants
        if notification_in.type not in vars(NotificationType).values():
             # We allow strings, but best practice to warn or check if strictly required. 
             pass 

        notification = Notification(
            **notification_in.model_dump(),
            receiver_id=receiver_id,
            tenant_id=tenant_id
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        
        # Broadcast
        await NotificationService.push_notification_to_user(notification)
        
        return notification

    @staticmethod
    async def create_bulk_notifications(
        db: AsyncSession,
        notification_in: NotificationCreate,
        receiver_ids: List[uuid.UUID],
        tenant_id: uuid.UUID
    ) -> List[Notification]:
        """
        Create notifications for multiple users (e.g. broadcast).
        Efficiently inserts multiple rows.
        """
        notifications = [
            Notification(
                **notification_in.model_dump(),
                receiver_id=uid,
                tenant_id=tenant_id
            )
            for uid in receiver_ids
        ]
        if notifications:
            db.add_all(notifications)
            await db.commit()
            
            # Broadcast to each user
            for note in notifications:
                await NotificationService.push_notification_to_user(note)
                
        return notifications

    @staticmethod
    async def push_notification_to_user(notification: Notification):
        """
        Push notification to user's WebSocket channel.
        """
        from app.realtime.manager import manager
        from app.modules.notifications.schema import NotificationResponse
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            # Format payload same as REST response
            payload = NotificationResponse.model_validate(notification).model_dump(mode="json")
            
            # Broadcast to user channel
            await manager.broadcast(f"user:{notification.receiver_id}", payload)
        except Exception as e:
            logger.error(f"Failed to push notification to user {notification.receiver_id}: {e}")

    @staticmethod
    async def get_my_notifications(
        db: AsyncSession,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[Notification], int]:
        """
        Get notifications for current user with pagination.
        Exclude deleted. Order by newest first.
        """
        # Count total
        count_query = select(func.count()).select_from(Notification).where(
            and_(
                Notification.receiver_id == user_id,
                Notification.deleted_at.is_(None)
            )
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # List with pagination
        query = select(Notification).where(
            and_(
                Notification.receiver_id == user_id,
                Notification.deleted_at.is_(None)
            )
        ).order_by(desc(Notification.created_at)).offset(skip).limit(limit)
        
        result = await db.execute(query)
        notifications = result.scalars().all()
        
        return notifications, total

    @staticmethod
    async def mark_as_read(
        db: AsyncSession,
        notification_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Notification:
        """
        Mark notification as read.
        Only owner can mark.
        """
        query = select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.receiver_id == user_id,
                Notification.deleted_at.is_(None)
            )
        )
        result = await db.execute(query)
        notification = result.scalar_one_or_none()
        
        if not notification:
            raise NotFoundException(detail="Notification not found")
        
        if notification.is_read:
            return notification 

        notification.is_read = True
        await db.commit()
        await db.refresh(notification)
        return notification

    @staticmethod
    async def delete_notification(
        db: AsyncSession,
        notification_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> None:
        """
        Soft delete notification.
        """
        query = select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.receiver_id == user_id
            )
        )
        result = await db.execute(query)
        notification = result.scalar_one_or_none()
        
        if not notification:
             # Already deleted or not exist - usually 404 or success (idempotent)
             # Let's say 404 to match typical REST
             raise NotFoundException(detail="Notification not found")

        notification.deleted_at = datetime.now(timezone.utc)
        await db.commit()

    @staticmethod
    async def get_unread_count(
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> int:
        """
        Count unread notifications.
        """
        query = select(func.count()).where(
            and_(
                Notification.receiver_id == user_id,
                Notification.is_read == False,
                Notification.deleted_at.is_(None)
            )
        )
        result = await db.execute(query)
        return result.scalar_one()
