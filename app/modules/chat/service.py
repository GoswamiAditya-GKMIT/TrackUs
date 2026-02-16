import logging
from typing import Sequence, Optional
import uuid

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.chat.model import GroupMessage, EventMessage
from app.modules.chat.schema import ChatMessageCreate
from app.modules.users.model import User
from app.modules.groups.service import MembershipService
from app.core.exceptions import PermissionDeniedException
from app.modules.groups.service import GroupService
from app.modules.chat.schema import ChatMessageResponse
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from app.common.enums import UserRole
from app.modules.events.service import EventService
from app.common.enums import ParticipantStatus
from app.modules.chat.model import EventMessage
from app.modules.chat.schema import EventMessageResponse





logger = logging.getLogger(__name__)


class ChatService:
    """
    Service for managing group chat messages and history.
    """

    @staticmethod
    async def create_message(
        db: AsyncSession,
        group_id: uuid.UUID,
        sender: User,
        message_data: ChatMessageCreate
    ) -> GroupMessage:
        """
        Create and persist a new chat message.
        Validates that the sender is an active member of the group.
        """
        # Validate active membership
        membership = await MembershipService.get_membership(db, group_id, sender.id)
        if not membership or membership.left_at is not None:
            raise PermissionDeniedException(
                detail="You must be an active member of the group to send messages"
            )

        message = GroupMessage(
            tenant_id=sender.tenant_id,
            group_id=group_id,
            sender_id=sender.id,
            message_type=message_data.message_type,
            message=message_data.message
        )
        
        db.add(message)
        await db.commit()
        
        # Fetch with sender info for broadcasting/response

        query = select(GroupMessage).options(
            selectinload(GroupMessage.sender)
        ).where(GroupMessage.id == message.id)
        
        result = await db.execute(query)
        message = result.scalar_one()
        
        logger.info(f"Message {message.id} sent by user {sender.id} in group {group_id}")
        return message

    @staticmethod
    async def list_messages(
        db: AsyncSession,
        group_id: uuid.UUID,
        user: User,
        skip: int = 0,
        limit: int = 50
    ) -> tuple[Sequence[GroupMessage], int]:
        """
        List chat messages for a group with pagination.
        Validates that the user is an active member or tenant admin.
        """
        # Permission check: Member or Tenant Admin
        # Reuse GroupService logic pattern or direct check
        await GroupService.get_group(db, group_id, user) # Verifies tenant isolation and existence

        # For regular users, verify membership
        if user.role != UserRole.TENANT_ADMIN:
            membership = await MembershipService.get_membership(db, group_id, user.id)
            if not membership or membership.left_at is not None:
                raise PermissionDeniedException(
                    detail="You do not have permission to view this group's messages"
                )

        base_query = select(GroupMessage).where(
            GroupMessage.group_id == group_id
        )

        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Data with sender info
        query = base_query.options(
            selectinload(GroupMessage.sender)
        ).order_by(GroupMessage.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        messages = result.scalars().all()
        
        return messages, total

    @staticmethod
    def get_broadcast_payload(message: GroupMessage) -> dict:
        """
        Prepare the payload for WebSocket broadcasting.
        """
        return ChatMessageResponse.model_validate(message).model_dump(mode="json")


class EventChatService:
    """
    Service for managing event chat messages and history.
    """

    @staticmethod
    async def create_message(
        db: AsyncSession,
        event_id: uuid.UUID,
        sender: User,
        message_data: ChatMessageCreate
    ) -> EventMessage:
        """
        Create and persist a new event chat message.
        Validates that the sender is an ACCEPTED participant of the event.
        """

        # Validate ACCEPTED participant status
        participant = await EventService._get_participant(db, event_id, sender.id)
        if not participant or participant.status != ParticipantStatus.ACCEPTED:
            raise PermissionDeniedException(
                detail="You must be an ACCEPTED participant to send messages"
            )

        message = EventMessage(
            tenant_id=sender.tenant_id,
            event_id=event_id,
            sender_id=sender.id,
            message_type=message_data.message_type,
            message=message_data.message
        )
        
        db.add(message)
        await db.commit()
        
        # Fetch with sender info for broadcasting/response
        query = select(EventMessage).options(
            selectinload(EventMessage.sender)
        ).where(EventMessage.id == message.id)
        
        result = await db.execute(query)
        message = result.scalar_one()
        
        logger.info(f"Message {message.id} sent by user {sender.id} in event {event_id}")
        return message

    @staticmethod
    async def list_messages(
        db: AsyncSession,
        event_id: uuid.UUID,
        user: User,
        skip: int = 0,
        limit: int = 50
    ) -> tuple[Sequence[EventMessage], int]:
        """
        List chat messages for an event with pagination.
        Validates that the user is an ACCEPTED participant.
        """
        from app.modules.events.service import EventService
        from app.common.enums import ParticipantStatus
        from app.modules.chat.model import EventMessage

        # Permission check: Must be ACCEPTED participant
        participant = await EventService._get_participant(db, event_id, user.id)
        if not participant or participant.status != ParticipantStatus.ACCEPTED:
             raise PermissionDeniedException(
                detail="You must be an ACCEPTED participant to view messages"
            )

        base_query = select(EventMessage).where(
            EventMessage.event_id == event_id
        )

        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Data with sender info
        query = base_query.options(
            selectinload(EventMessage.sender)
        ).order_by(EventMessage.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        messages = result.scalars().all()
        
        return messages, total

    @staticmethod
    def get_broadcast_payload(message: EventMessage) -> dict:
        """
        Prepare the payload for WebSocket broadcasting.
        """
        return EventMessageResponse.model_validate(message).model_dump(mode="json")
