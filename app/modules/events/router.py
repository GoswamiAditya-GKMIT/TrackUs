"""
Travel Event router - HTTP endpoints for event management.
"""
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user, restrict_super_admin
from app.dependencies.groups import require_group_admin, require_group_member
from app.dependencies.events import get_accessible_event, require_event_admin
from app.modules.users.model import User
from app.modules.groups.model import GroupMember
from app.modules.events.model import TravelEvent
from app.modules.events.service import EventService
from app.modules.events.schema import EventCreate, EventResponse, ParticipantResponse, ParticipantAddRequest, EventUpdate
from app.common.response_utils import success_response, paginated_response
from app.common.responses import SuccessResponse, PaginatedResponse
from app.dependencies.common import PaginationParams

router = APIRouter(tags=["events"])


@router.post(
    "/groups/{group_id}/events",
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
    "/groups/{group_id}/events",
    response_model=PaginatedResponse[EventResponse],
    summary="List all events in a group",
    dependencies=[Depends(restrict_super_admin)]
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


@router.patch(
    "/events/{event_id}",
    response_model=SuccessResponse[EventResponse],
    summary="Update an event"
)
async def update_event(
    event_id: uuid.UUID,
    update_data: EventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an event.
    Permissions: Event creator or group admin only
    Returns: Updated event
    """
    event = await EventService.update_event(
        db=db,
        event_id=event_id,
        update_data=update_data,
        user=current_user
    )
    
    return success_response(
        message="Event updated successfully",
        data=EventResponse.model_validate(event)
    )


# Participant Management Endpoints

@router.get(
    "/events/{event_id}/participants",
    response_model=PaginatedResponse[ParticipantResponse],
    summary="List all participants of an event",
    dependencies=[Depends(restrict_super_admin)]
)
async def list_participants(
    event_id: uuid.UUID,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    event: TravelEvent = Depends(get_accessible_event)
):
    """
    List all participants of an event.
    Permissions: Active group member
    Returns: Paginated list of participants with their status
    """
    participants, total = await EventService.list_participants(
        db=db, 
        event_id=event_id,
        skip=pagination.skip,
        limit=pagination.limit
    )
    
    return paginated_response(
        message="Participants retrieved successfully",
        data=[ParticipantResponse.model_validate(p) for p in participants],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )


@router.post(
    "/events/{event_id}/accept",
    response_model=SuccessResponse[ParticipantResponse],
    summary="Accept event invitation"
)
async def accept_invitation(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    event: TravelEvent = Depends(get_accessible_event)
):
    """
    Accept an event invitation.
    Permissions: Invited user only
    Returns: Updated participant status
    """
    participant = await EventService.accept_invitation(
        db=db,
        event_id=event_id,
        user=current_user
    )
    
    return success_response(
        message="Invitation accepted successfully",
        data=ParticipantResponse.model_validate(participant)
    )


@router.post(
    "/events/{event_id}/reject",
    response_model=SuccessResponse[ParticipantResponse],
    summary="Reject event invitation"
)
async def reject_invitation(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    event: TravelEvent = Depends(get_accessible_event)
):
    """
    Reject an event invitation.
    Permissions: Invited user only
    Returns: Updated participant status
    """
    participant = await EventService.reject_invitation(
        db=db,
        event_id=event_id,
        user=current_user
    )
    
    return success_response(
        message="Invitation rejected successfully",
        data=ParticipantResponse.model_validate(participant)
    )


@router.post(
    "/events/{event_id}/leave",
    response_model=SuccessResponse[ParticipantResponse],
    summary="Leave an event"
)
async def leave_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    event: TravelEvent = Depends(get_accessible_event)
):
    """
    Leave an event.
    Permissions: Accepted participant only
    Returns: Updated participant status
    """
    participant = await EventService.leave_event(
        db=db,
        event_id=event_id,
        user=current_user
    )
    
    return success_response(
        message="You have left the event",
        data=ParticipantResponse.model_validate(participant)
    )


@router.post(
    "/events/{event_id}/participants",
    response_model=SuccessResponse[ParticipantResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add a participant to an event (Admin only)"
)
async def add_participant(
    event_id: uuid.UUID,
    request: ParticipantAddRequest,
    db: AsyncSession = Depends(get_db),
    event: TravelEvent = Depends(require_event_admin)
):
    """
    Add a participant to an event.
    Permissions: Group admin or event creator only
    Returns: Created participant
    """
    participant = await EventService.add_participant(
        db=db,
        event_id=event_id,
        target_user_id=request.user_id,
        event=event
    )
    
    return success_response(
        message="Participant added successfully",
        data=ParticipantResponse.model_validate(participant)
    )


@router.delete(
    "/events/{event_id}/participants/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a participant from an event (Admin only)"
)
async def remove_participant(
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    event: TravelEvent = Depends(require_event_admin)
):
    """
    Remove a participant from an event.
    Permissions: Group admin or event creator only
    Returns: 204 No Content
    """
    await EventService.remove_participant(
        db=db,
        event_id=event_id,
        target_user_id=user_id
    )
    
    return None
