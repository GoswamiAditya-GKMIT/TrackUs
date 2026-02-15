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

from app.modules.events.model import TravelEvent, EventParticipant
from app.common.enums import EventStatus, ParticipantStatus
from app.modules.events.schema import EventCreate, EventUpdate
from app.modules.groups.model import Group, GroupMember
from app.modules.users.model import User
from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
    PermissionDeniedException,
    TenantIsolationException
)

logger = logging.getLogger(__name__)


class EventService:
    """Service for managing travel events and participants."""

    # ==================== Event Management Methods ====================

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
            status=EventStatus.PLANNED,
            created_by=creator.id
        )
        
        db.add(event)
        await db.flush()  # Flush to get event.id
        
        # Auto-invite all group members
        # Fetch all group members
        members_query = select(GroupMember).where(
            and_(
                GroupMember.group_id == group_id,
                GroupMember.left_at.is_(None)
            )
        )
        members_result = await db.execute(members_query)
        members = members_result.scalars().all()
        
        # Create participant records
        for member in members:
            # Creator is auto-accepted, others are invited
            if member.user_id == creator.id:
                status = ParticipantStatus.ACCEPTED
                responded_at = datetime.now(timezone.utc)
            else:
                status = ParticipantStatus.INVITED
                responded_at = None
            
            participant = EventParticipant(
                event_id=event.id,
                user_id=member.user_id,
                status=status,
                responded_at=responded_at
            )
            db.add(participant)
        
        await db.commit()
        
        # Reload event with relationships
        query = select(TravelEvent).options(
            selectinload(TravelEvent.creator),
            selectinload(TravelEvent.group),
            selectinload(TravelEvent.tenant)
        ).where(TravelEvent.id == event.id)
        
        result = await db.execute(query)
        event = result.scalar_one()
        
        logger.info(
            f"Event {event.id} created by user {creator.id} in group {group_id} "
            f"with {len(members)} participants auto-invited"
        )
        
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

    # ==================== Participant Management Methods ====================

    @staticmethod
    async def list_participants(
        db: AsyncSession,
        event_id: uuid.UUID
    ) -> Sequence[EventParticipant]:
        """
        List all participants for an event.
        """
        query = select(EventParticipant).options(
            selectinload(EventParticipant.user),
            selectinload(EventParticipant.event)
        ).where(
            EventParticipant.event_id == event_id
        ).order_by(EventParticipant.created_at.asc())
        
        result = await db.execute(query)
        participants = result.scalars().all()
        
        logger.info(f"Listed {len(participants)} participants for event {event_id}")
        
        return participants
    
    @staticmethod
    async def _get_participant(
        db: AsyncSession,
        event_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Optional[EventParticipant]:
        """Helper to get a participant record."""
        query = select(EventParticipant).options(
            selectinload(EventParticipant.user),
            selectinload(EventParticipant.event)
        ).where(
            and_(
                EventParticipant.event_id == event_id,
                EventParticipant.user_id == user_id
            )
        )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def _validate_state_transition(
        current_status: ParticipantStatus,
        new_status: ParticipantStatus,
        action: str
    ) -> None:
        """
        Validate state transitions.
        
        Valid transitions:
        - INVITED → ACCEPTED
        - INVITED → REJECTED
        - ACCEPTED → LEFT
        - ANY → REMOVED (admin only)
        """
        valid_transitions = {
            (ParticipantStatus.INVITED, ParticipantStatus.ACCEPTED),
            (ParticipantStatus.INVITED, ParticipantStatus.REJECTED),
            (ParticipantStatus.ACCEPTED, ParticipantStatus.LEFT),
        }
        
        # REMOVED can be from any state (admin action)
        if new_status == ParticipantStatus.REMOVED:
            return
        
        if (current_status, new_status) not in valid_transitions:
            raise BadRequestException(
                detail=f"Cannot {action} from current status '{current_status}'"
            )
    
    @staticmethod
    async def accept_invitation(
        db: AsyncSession,
        event_id: uuid.UUID,
        user: User
    ) -> EventParticipant:
        """
        Accept event invitation.
        """
        participant = await EventService._get_participant(db, event_id, user.id)
        
        if not participant:
            raise NotFoundException(detail="You are not invited to this event")
        
        # Validate state transition
        await EventService._validate_state_transition(
            participant.status,
            ParticipantStatus.ACCEPTED,
            "accept invitation"
        )
        
        # Update status
        participant.status = ParticipantStatus.ACCEPTED
        participant.responded_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(participant)
        
        logger.info(f"User {user.id} accepted invitation to event {event_id}")
        
        return participant
    
    @staticmethod
    async def reject_invitation(
        db: AsyncSession,
        event_id: uuid.UUID,
        user: User
    ) -> EventParticipant:
        """
        Reject event invitation.
        """
        participant = await EventService._get_participant(db, event_id, user.id)
        
        if not participant:
            raise NotFoundException(detail="You are not invited to this event")
        
        # Validate state transition
        await EventService._validate_state_transition(
            participant.status,
            ParticipantStatus.REJECTED,
            "reject invitation"
        )
        
        # Update status
        participant.status = ParticipantStatus.REJECTED
        participant.responded_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(participant)
        
        logger.info(f"User {user.id} rejected invitation to event {event_id}")
        
        return participant
    
    @staticmethod
    async def leave_event(
        db: AsyncSession,
        event_id: uuid.UUID,
        user: User
    ) -> EventParticipant:
        """
        Leave an event.
        """
        participant = await EventService._get_participant(db, event_id, user.id)
        
        if not participant:
            raise NotFoundException(detail="You are not a participant of this event")

        # Prevent event creator from leaving
        if participant.event.created_by == user.id:
            raise BadRequestException(detail="Event creator cannot leave the event")
        
        # Validate state transition
        await EventService._validate_state_transition(
            participant.status,
            ParticipantStatus.LEFT,
            "leave event"
        )
        
        # Update status
        participant.status = ParticipantStatus.LEFT
        participant.responded_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(participant)
        
        logger.info(f"User {user.id} left event {event_id}")
        
        return participant
    
    @staticmethod
    async def add_participant(
        db: AsyncSession,
        event_id: uuid.UUID,
        target_user_id: uuid.UUID,
        event: TravelEvent
    ) -> EventParticipant:
        """
        Add a participant to an event (admin only).
        """
        # Check if user is a group member
        member_query = select(GroupMember).where(
            and_(
                GroupMember.group_id == event.group_id,
                GroupMember.user_id == target_user_id,
                GroupMember.left_at.is_(None)
            )
        )
        member_result = await db.execute(member_query)
        member = member_result.scalar_one_or_none()
        
        if not member:
            raise BadRequestException(detail="User is not a member of this group")
        
        # Check if already a participant
        existing = await EventService._get_participant(db, event_id, target_user_id)
        if existing:
            raise BadRequestException(detail="User is already a participant")
        
        # Create participant
        participant = EventParticipant(
            event_id=event_id,
            user_id=target_user_id,
            status=ParticipantStatus.INVITED
        )
        
        db.add(participant)
        await db.commit()
        await db.refresh(participant)
        
        logger.info(f"User {target_user_id} added to event {event_id} by admin")
        
        return participant
    
    @staticmethod
    async def remove_participant(
        db: AsyncSession,
        event_id: uuid.UUID,
        target_user_id: uuid.UUID
    ) -> None:
        """
        Remove a participant from an event (admin only).
        """
        participant = await EventService._get_participant(db, event_id, target_user_id)
        
        if not participant:
            raise NotFoundException(detail="Participant not found")

        # Prevent removal of event creator
        if participant.event.created_by == target_user_id:
            raise BadRequestException(detail="Event creator cannot be removed from the event")
        
        # Update status to REMOVED
        participant.status = ParticipantStatus.REMOVED
        participant.responded_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        logger.info(f"User {target_user_id} removed from event {event_id} by admin")


__all__ = ["EventService"]
