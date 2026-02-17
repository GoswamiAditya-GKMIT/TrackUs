
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.chat.schema import ChatMessageCreate, ChatMessageResponse, EventMessageResponse
from app.modules.chat.service import ChatService, EventChatService
from app.modules.users.model import User
from app.modules.events.model import TravelEvent
from app.dependencies.auth import get_current_user, restrict_super_admin
from app.dependencies.events import get_accessible_event
from app.dependencies.common import PaginationParams
from app.common.response_utils import success_response, paginated_response
from app.common.responses import SuccessResponse, PaginatedResponse
from app.realtime.manager import manager


router = APIRouter(tags=["chat"])


@router.post(
    "/groups/{group_id}/messages",
    response_model=SuccessResponse[ChatMessageResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Send a message to a group"
)
async def send_message(
    group_id: uuid.UUID,
    message_data: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send a new message to the specified group.
    Requires active membership in the group.
    """
    message = await ChatService.create_message(
        db, group_id, current_user, message_data
    )
    return success_response(
        message="Message sent successfully",
        data=ChatMessageResponse.model_validate(message)
    )


@router.get(
    "/groups/{group_id}/messages",
    response_model=PaginatedResponse[ChatMessageResponse],
    summary="Get group message history",
    dependencies=[Depends(restrict_super_admin)]
)
async def get_chat_history(
    group_id: uuid.UUID,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve paginated message history for a group.
    Requires membership or tenant admin access.
    """
    messages, total = await ChatService.list_messages(
        db, group_id, current_user, pagination.skip, pagination.limit
    )
    
    return paginated_response(
        message="Chat history retrieved successfully",
        data=[ChatMessageResponse.model_validate(m) for m in messages],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )


@router.post(
    "/events/{event_id}/messages",
    response_model=SuccessResponse[EventMessageResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Send a message to event chat"
)
async def send_event_message(
    event_id: uuid.UUID,
    message_data: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    event: TravelEvent = Depends(get_accessible_event)
):
    """
    Send a message to the event chat.
    Permissions: Accepted participant only
    Returns: Created message
    """
    message = await EventChatService.create_message(
        db=db,
        event_id=event_id,
        sender=current_user,
        message_data=message_data
    )
    
    # Broadcast to WebSocket listeners
    try:
        payload = EventChatService.get_broadcast_payload(message)
        await manager.broadcast(str(event_id), payload)
    except Exception as e:
        pass
        
    return success_response(
        message="Message sent successfully",
        data=EventMessageResponse.model_validate(message)
    )


@router.get(
    "/events/{event_id}/messages",
    response_model=PaginatedResponse[EventMessageResponse],
    summary="List event chat messages",
    dependencies=[Depends(restrict_super_admin)]
)
async def list_event_messages(
    event_id: uuid.UUID,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    event: TravelEvent = Depends(get_accessible_event)
):
    """
    List chat messages for an event.
    Permissions: Accepted participant only
    Returns: Paginated list of messages
    """
    messages, total = await EventChatService.list_messages(
        db=db,
        event_id=event_id,
        user=current_user,
        skip=pagination.skip,
        limit=pagination.limit
    )
    
    return paginated_response(
        message="Messages retrieved successfully",
        data=[EventMessageResponse.model_validate(msg) for msg in messages],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )
