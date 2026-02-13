"""
Travel Event router - HTTP endpoints for event management.
"""
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.groups import require_group_admin, require_group_member
from app.modules.users.model import User
from app.modules.groups.model import GroupMember
from app.modules.events.service import EventService
from app.modules.events.schema import EventCreate, EventResponse
from app.common.response_utils import success_response, paginated_response
from app.common.responses import SuccessResponse, PaginatedResponse
from app.dependencies.common import PaginationParams

router = APIRouter(prefix="/groups", tags=["events"])


@router.post(
    "/{group_id}/events",
    response_model=SuccessResponse[EventResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new event in a group"
)
async def create_event(
    group_id: uuid.UUID,
    event_data: EventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: GroupMember = Depends(require_group_admin)
):
    """
    Create a new travel event in a group.
    Permissions: Group Admin only
    Returns: Created event details
    """
    event = await EventService.create_event(
        db=db,
        group_id=group_id,
        event_data=event_data,
        creator=current_user
    )
    
    return success_response(
        message="Event created successfully",
        data=EventResponse.model_validate(event)
    )


@router.get(
    "/{group_id}/events",
    response_model=PaginatedResponse[EventResponse],
    summary="List all events in a group"
)
async def list_events(
    group_id: uuid.UUID,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    membership: GroupMember = Depends(require_group_member)
):
    """
    List all events in a group, ordered by start time (newest first).
    Permissions: Active group member
    Returns: Paginated list of events
    """
    events, total = await EventService.list_events(
        db=db,
        group_id=group_id,
        skip=pagination.skip,
        limit=pagination.limit
    )
    
    return paginated_response(
        message="Events retrieved successfully",
        data=[EventResponse.model_validate(event) for event in events],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )
