"""
Travel Event service layer.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Sequence
import uuid

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.events.model import TravelEvent
from app.common.enums import EventStatus
from app.modules.events.schema import EventCreate, EventUpdate
from app.modules.groups.model import Group
from app.modules.users.model import User
from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
    PermissionDeniedException,
    TenantIsolationException
)

logger = logging.getLogger(__name__)


class EventService:

    @staticmethod
    async def create_event(
        db: AsyncSession,
        group_id: uuid.UUID,
        event_data: EventCreate,
        creator: User
    ) -> TravelEvent:
        """
        Create a new travel event in a group.
        Args:
            db: Database session
            group_id: Group ID
            event_data: Event creation data
            creator: User creating the event  
        Returns:
            Created TravelEvent
        Raises:
            NotFoundException: If group not found
            TenantIsolationException: If tenant mismatch
            BadRequestException: If invalid time range
        """
        query = select(Group).options(
            selectinload(Group.tenant)
        ).where(
            and_(
                Group.id == group_id,
                Group.deleted_at.is_(None)
            )
        )
        result = await db.execute(query)
        group = result.scalar_one_or_none()
        
        if not group:
            raise NotFoundException(detail="Group not found")
        
        if group.tenant_id != creator.tenant_id:
            raise TenantIsolationException(
                detail="Cannot create event in group from different tenant"
            )
        
        if event_data.end_time <= event_data.start_time:
            raise BadRequestException(detail="End time must be after start time")
        
        existing_event_query = select(TravelEvent).where(
            and_(
                TravelEvent.group_id == group_id,
                TravelEvent.name == event_data.name,
                TravelEvent.deleted_at.is_(None)
            )
        )
        existing_result = await db.execute(existing_event_query)
        existing_event = existing_result.scalar_one_or_none()
        
        if existing_event:
            raise BadRequestException(
                detail=f"Event with name '{event_data.name}' already exists in this group"
            )
        
        # Create event
        event = TravelEvent(
            tenant_id=creator.tenant_id,
            group_id=group_id,
            name=event_data.name,
            destination=event_data.destination,
            start_time=event_data.start_time,
            end_time=event_data.end_time,
            status=EventStatus.PLANNED.value,
            created_by=creator.id
        )
        
        db.add(event)
        await db.commit()
        
        query = select(TravelEvent).options(
            selectinload(TravelEvent.creator),
            selectinload(TravelEvent.group),
            selectinload(TravelEvent.tenant)
        ).where(TravelEvent.id == event.id)
        
        result = await db.execute(query)
        event = result.scalar_one()
        
        
        return event

    @staticmethod
    async def list_events(
        db: AsyncSession,
        group_id: uuid.UUID,
        skip: int = 0,
        limit: int = 10
    ) -> tuple[Sequence[TravelEvent], int]:
        """
        List all events in a group, ordered by start_time descending.
        Args:
            db: Database session
            group_id: Group ID
            skip: Number of records to skip
            limit: Maximum number of records to return  
        Returns:
            Tuple of (events list, total count)
        """
        count_query = select(func.count()).select_from(TravelEvent).where(
            and_(
                TravelEvent.group_id == group_id,
                TravelEvent.deleted_at.is_(None)
            )
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        query = select(TravelEvent).options(
            selectinload(TravelEvent.creator),
            selectinload(TravelEvent.group)
        ).where(
            and_(
                TravelEvent.group_id == group_id,
                TravelEvent.deleted_at.is_(None)
            )
        ).order_by(
            TravelEvent.start_time.desc()
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        events = result.scalars().all()
                
        return events, total

    @staticmethod
    async def get_event(
        db: AsyncSession,
        event_id: uuid.UUID
    ) -> Optional[TravelEvent]:
        """
        Get a single event by ID.
        Args:
            db: Database session
            event_id: Event ID  
        Returns:
            TravelEvent or None if not found
        """
        query = select(TravelEvent).options(
            selectinload(TravelEvent.creator),
            selectinload(TravelEvent.group),
            selectinload(TravelEvent.tenant)
        ).where(
            and_(
                TravelEvent.id == event_id,
                TravelEvent.deleted_at.is_(None)
            )
        )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
