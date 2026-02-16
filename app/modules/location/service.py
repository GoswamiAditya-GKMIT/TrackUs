"""
Live Location Service.
"""
import logging
from datetime import datetime, timezone
import uuid
from typing import Sequence, Optional

from sqlalchemy import select, and_, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.location.model import LiveLocation
from app.modules.location.schema import LocationUpdate
from app.modules.events.model import TravelEvent, EventParticipant
from app.common.enums import EventStatus, ParticipantStatus
from app.core.exceptions import (
    NotFoundException,
    PermissionDeniedException,
    BadRequestException
)
from app.realtime.manager import manager

logger = logging.getLogger(__name__)


class LocationService:
    """Service for managing live location sharing."""

    @staticmethod
    async def _validate_permissions(
        db: AsyncSession,
        event_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> None:
        """
        Validate that user can share location in this event.
        Rules:
        1. Event must exist and be active (PLANNED or ONGOING).
        """
        event_query = select(TravelEvent).where(TravelEvent.id == event_id)
        result = await db.execute(event_query)
        event = result.scalar_one_or_none()

        if not event:
            raise NotFoundException(detail="Event not found")

        if event.status != EventStatus.ONGOING:
             raise PermissionDeniedException(
                 detail=f"Cannot share location for event in {event.status} state. Event must be ONGOING."
             )

        # 2. Fetch Participant Status
        participant_query = select(EventParticipant).where(
            and_(
                EventParticipant.event_id == event_id,
                EventParticipant.user_id == user_id
            )
        )
        p_result = await db.execute(participant_query)
        participant = p_result.scalar_one_or_none()

        if not participant:
             raise PermissionDeniedException(detail="User is not a participant of this event")

        if participant.status != ParticipantStatus.ACCEPTED:
             raise PermissionDeniedException(
                 detail="Only ACCEPTED participants can share location"
             )

    @staticmethod
    async def update_location(
        db: AsyncSession,
        event_id: uuid.UUID,
        user_id: uuid.UUID,
        location_data: LocationUpdate
    ) -> LiveLocation:
        """
        Update user's live location.
        Upserts the LiveLocation record and broadcasts via WebSocket.
        """
        # Validate permissions
        await LocationService._validate_permissions(db, event_id, user_id)

        # Check for existing location record
        query = select(LiveLocation).where(
            and_(
                LiveLocation.event_id == event_id,
                LiveLocation.user_id == user_id
            )
        )
        result = await db.execute(query)
        location = result.scalar_one_or_none()
        
        timestamp = datetime.now(timezone.utc)

        if location:
            location.latitude = location_data.latitude
            location.longitude = location_data.longitude
            location.is_active = True
            location.last_updated_at = timestamp
        else:
            event_q = select(TravelEvent.tenant_id).where(TravelEvent.id == event_id)
            tenant_id = (await db.execute(event_q)).scalar_one()

            location = LiveLocation(
                tenant_id=tenant_id,
                event_id=event_id,
                user_id=user_id,
                latitude=location_data.latitude,
                longitude=location_data.longitude,
                is_active=True,
                last_updated_at=timestamp
            )
            db.add(location)

        await db.commit()
        await db.refresh(location)

        # Broadcast update
        payload = {
            "type": "location_update",
            "event_id": str(event_id),
            "user_id": str(user_id),
            "latitude": location.latitude,
            "longitude": location.longitude,
            "is_active": True,
            "updated_at": location.last_updated_at.isoformat()
        }
        
        await manager.broadcast(str(event_id), payload)

        return location

    @staticmethod
    async def get_user_location(
        db: AsyncSession, event_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[LiveLocation]:
        """
        Get the current active location for a specific user in an event.
        """
        query = select(LiveLocation).where(
            and_(
                LiveLocation.event_id == event_id,
                LiveLocation.user_id == user_id
                )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_event_locations(
        db: AsyncSession,
        event_id: uuid.UUID,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[Sequence[LiveLocation], int]:
        """
        Get locations for an event with pagination.
        If active_only is True, returns only currently sharing users.
        If active_only is False, returns all users' last known locations.
        """
        # Base query for filtering
        base_query = select(LiveLocation).where(LiveLocation.event_id == event_id)
        if active_only:
            base_query = base_query.where(LiveLocation.is_active == True)

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # List with pagination
        query = base_query.options(
            selectinload(LiveLocation.user)
        ).offset(skip).limit(limit)

        result = await db.execute(query)
        locations = result.scalars().all()
        
        return locations, total

    @staticmethod
    async def stop_sharing(
        db: AsyncSession,
        event_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> None:
        """
        Stop sharing location (mark inactive).
        """
        query = select(LiveLocation).where(
            and_(
                LiveLocation.event_id == event_id,
                LiveLocation.user_id == user_id
            )
        )
        result = await db.execute(query)
        location = result.scalar_one_or_none()

        if location and location.is_active:
            location.is_active = False
            location.last_updated_at = datetime.now(timezone.utc)
            await db.commit()

            # Broadcast stop
            payload = {
                "type": "location_stop",
                "event_id": str(event_id),
                "user_id": str(user_id),
                "is_active": False,
                "updated_at": location.last_updated_at.isoformat()
            }
            await manager.broadcast(str(event_id), payload)
