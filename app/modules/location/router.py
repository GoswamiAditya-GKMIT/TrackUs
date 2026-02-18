"""
Live Location Router.
"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedException, NotFoundException
from app.db.session import get_db
from app.modules.users.model import User
from app.dependencies.auth import get_current_user
from app.common.response_utils import success_response, SuccessResponse, paginated_response
from app.common.responses import PaginatedResponse
from app.dependencies.common import PaginationParams
from app.modules.location.service import LocationService
from app.modules.location.schema import LocationResponse
from app.realtime.location_simulator import LocationSimulator
from app.modules.events.service import EventService

router = APIRouter(prefix="/events/{event_id}", tags=["location"])


@router.get(
    "/locations",
    response_model=PaginatedResponse[LocationResponse],
    summary="Get locations for an event"
)
async def get_event_locations(
    event_id: uuid.UUID,
    pagination: PaginationParams = Depends(),
    active_only: bool = Query(False, description="Filter for currently active locations only"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all user locations for a specific event.
    By default (active_only=False), returns last known location of all users.
    If active_only=True, returns only currently sharing users.
    """
    participant = await EventService._get_participant(db, event_id, current_user.id)
    if not participant:
         raise PermissionDeniedException(detail="You are not a participant of this event")

    locations, total = await LocationService.get_event_locations(
        db, 
        event_id, 
        tenant_id=current_user.tenant_id,
        active_only=active_only,
        skip=pagination.skip,
        limit=pagination.limit
    )
    
    return paginated_response(
        message="Locations retrieved successfully",
        data=[LocationResponse.model_validate(loc) for loc in locations],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )


@router.get(
    "/locations/{user_id}",
    response_model=SuccessResponse[LocationResponse],
    summary="Get active location for a specific user"
)
async def get_specific_user_location(
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the current active location for a specific user in an event.
    """
    participant = await EventService._get_participant(db, event_id, current_user.id)
    if not participant:
         raise PermissionDeniedException(detail="You are not a participant of this event")

    location = await LocationService.get_user_location(db, event_id, user_id, current_user.tenant_id)
    
    if not location:
        raise NotFoundException(detail="Location not found for this user")

    return success_response(
        message="Location retrieved successfully",
        data=LocationResponse.model_validate(location)
    )


@router.delete(
    "/locations/me",
    response_model=SuccessResponse[None],
    summary="Stop sharing location"
)
async def stop_sharing_location(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Stop sharing live location for the current user.
    """
    await LocationService.stop_sharing(db, event_id, current_user.id, current_user.tenant_id)
    return success_response(message="Location sharing stopped", data=None)

@router.post(
    "/locations/{user_id}/simulation",
    response_model=SuccessResponse[dict],
    summary="Start location simulation"
)
async def start_simulate_location(
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Start location simulation for a user.
    """
    # Check if target user exists and is participant
    participant = await EventService._get_participant(db, event_id, user_id)
    if not participant:
        raise NotFoundException(detail="Target user is not a participant")
        
    started = await LocationSimulator.start_simulation(event_id, user_id, current_user.tenant_id)
    if started:
        return success_response(message="Simulation started", data={"status": "running"})
    else:
        return success_response(message="Simulation already running", data={"status": "running"})


@router.delete(
    "/locations/{user_id}/simulation",
    response_model=SuccessResponse[dict],
    summary="Stop location simulation"
)
async def stop_simulate_location(
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Stop location simulation for a user.
    """
    # Check if target user exists and is participant
    participant = await EventService._get_participant(db, event_id, user_id)
    if not participant:
        raise NotFoundException(detail="Target user is not a participant")

    stopped = await LocationSimulator.stop_simulation(event_id, user_id, current_user.tenant_id)
    if stopped:
        return success_response(message="Simulation stopped", data={"status": "stopped"})
    else:
        return success_response(message="Simulation was not running", data={"status": "stopped"})
