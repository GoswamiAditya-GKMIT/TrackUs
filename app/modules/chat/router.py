"""
Chat router - HTTP endpoints for group messages.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.chat.schema import ChatMessageCreate, ChatMessageResponse
from app.modules.chat.service import ChatService
from app.modules.users.model import User
from app.dependencies.auth import get_current_user
from app.dependencies.common import PaginationParams
from app.common.response_utils import success_response, paginated_response
from app.common.responses import SuccessResponse, PaginatedResponse

router = APIRouter(prefix="/groups", tags=["chat"])


@router.post(
    "/{group_id}/messages",
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
    "/{group_id}/messages",
    response_model=PaginatedResponse[ChatMessageResponse],
    summary="Get group message history"
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
