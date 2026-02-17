"""
Notification Router.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, Path, Body, status, Response

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.modules.users.model import User
from app.common.responses import SuccessResponse, PaginatedResponse
from app.common.response_utils import paginated_response
from app.dependencies.common import PaginationParams

from app.modules.notifications.schema import (
    NotificationResponse,
    UnreadCountResponse,
    NotificationUpdate
)
from app.modules.notifications.service import NotificationService

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"]
)

@router.get(
    "",
    response_model=PaginatedResponse[NotificationResponse],
    summary="List my notifications"
)
async def list_my_notifications(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get notifications for the current user.
    Newest first.
    """
    notifications, total = await NotificationService.get_my_notifications(
        db, 
        user_id=current_user.id,
        skip=pagination.skip,
        limit=pagination.limit
    )
    
    return paginated_response(
        message="Notifications retrieved successfully",
        data=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )

@router.get(
    "/unread-count",
    response_model=SuccessResponse[UnreadCountResponse],
    summary="Get unread count"
)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the count of unread notifications.
    """
    count = await NotificationService.get_unread_count(db, current_user.id)
    return SuccessResponse(message="Unread count retrieved successfully", data={"count": count})

@router.patch(
    "/{notification_id}",
    response_model=SuccessResponse[NotificationResponse],
    summary="Mark as read"
)
async def mark_as_read(
    notification_id: UUID = Path(...),
    payload: NotificationUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark a notification as read.
    Only allows updating `is_read`.
    """
    
    notification = await NotificationService.mark_as_read(
        db,
        notification_id,
        current_user.id
    )
    return SuccessResponse(message="Notification marked as read", data=notification)

@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete notification"
)
async def delete_notification(
    notification_id: UUID = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Soft delete a notification.
    """
    await NotificationService.delete_notification(
        db,
        notification_id,
        current_user.id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
