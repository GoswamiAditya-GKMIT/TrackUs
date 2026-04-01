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
from app.common.enums import EventStatus, ParticipantStatus, GroupMemberRole, UserRole
from app.modules.events.schema import EventCreate, EventUpdate
from app.modules.groups.model import Group, GroupMember
from app.modules.users.model import User
from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
    PermissionDeniedException,
    TenantIsolationException
)
from app.modules.notifications.service import NotificationService
from app.modules.notifications.schema import NotificationCreate
from app.common.constants import NotificationType, ReferenceType
from app.modules.groups.service import GroupService
from app.common.utils import apply_tenant_filter

logger = logging.getLogger(__name__)



class EventService:
    """Service for managing travel events and participants."""

    # Event Management Methods

    @staticmethod
    async def create_event(
        db: AsyncSession,
        group_id: uuid.UUID,
        event_data: EventCreate,
        creator: User
    ) -> TravelEvent:
        """
        Create a new travel event in a group.
        """
        query = select(Group).options(
            selectinload(Group.tenant)
        ).where(
            and_(
                Group.id == group_id,
                Group.deleted_at.is_(None)
            )
        )
        
        query = apply_tenant_filter(query, creator, Group)
        
        result = await db.execute(query)
        group = result.scalar_one_or_none()
        
        if not group:
            raise NotFoundException(detail="Group not found")
        
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
            selectinload(TravelEvent.tenant),
            selectinload(TravelEvent.participants)
        ).where(TravelEvent.id == event.id)
        
        result = await db.execute(query)
        event = result.scalar_one()
        
        logger.info(
            f"Event {event.id} created by user {creator.id} in group {group_id} "
            f"with {len(members)} participants auto-invited"
        )
        
        
        
        invited_ids = [m.user_id for m in members if m.user_id != creator.id]
        logger.info(f"Found {len(members)} entries. Creator: {creator.id}. Invited candidates: {len(invited_ids)}")
        if invited_ids:
            try:
                await NotificationService.create_bulk_notifications(
                    db,
                    NotificationCreate(
                        type=NotificationType.EVENT_INVITED,
                        title=f"New Event: {event.name}",
                        message=f"You have been invited to event '{event.name}'",
                        reference_type=ReferenceType.EVENT,
                        reference_id=event.id
                    ),
                    receiver_ids=invited_ids,
                    tenant_id=creator.tenant_id
                )
            except Exception as e:
                logger.error(f"Failed to send notifications for event create: {e}")
        
        return event

    @staticmethod
    async def list_events(
        db: AsyncSession,
        group_id: uuid.UUID,
        current_user: User,
        skip: int = 0,
        limit: int = 10,
        deleted: Optional[bool] = None
    ) -> tuple[Sequence[TravelEvent], int]:
        """
        List all events in a group, ordered by start_time descending.
        Admins can optionally see deleted events. Regular users only see active ones.
        """
        # Regular users cannot see deleted events
        if current_user.role == UserRole.USER:
            deleted = False

        base_query = select(TravelEvent).where(TravelEvent.group_id == group_id)

        # Handle soft-delete filtering
        if deleted is True:
            base_query = base_query.where(TravelEvent.deleted_at.is_not(None))
        elif deleted is False:
            base_query = base_query.where(TravelEvent.deleted_at.is_(None))
        # If None, show both (admins only)

        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        query = base_query.options(
            selectinload(TravelEvent.creator),
            selectinload(TravelEvent.group),
            selectinload(TravelEvent.participants)
        ).order_by(
            TravelEvent.start_time.desc()
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        events = result.scalars().all()
                
        return events, total

    @staticmethod
    async def get_event(
        db: AsyncSession,
        event_id: uuid.UUID,
        user: User
    ) -> Optional[TravelEvent]:
        """
        Get a single event by ID.
        Args:
            db: Database session
            event_id: Event ID 
            user: User 
        Returns:
            TravelEvent or None if not found
        """
        query = select(TravelEvent).options(
            selectinload(TravelEvent.creator),
            selectinload(TravelEvent.group),
            selectinload(TravelEvent.tenant),
            selectinload(TravelEvent.participants)
        ).where(
            and_(
                TravelEvent.id == event_id,
                TravelEvent.deleted_at.is_(None)
            )
        )
        
        query = apply_tenant_filter(query, user, TravelEvent)
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
        
    @staticmethod
    def _validate_status_transition(
        current_status: EventStatus,
        new_status: EventStatus
    ) -> None:
        """
        Validate event status transitions.
        
        Valid transitions:
        - PLANNED → ONGOING
        - PLANNED → CANCELLED
        - ONGOING → COMPLETED
        - ONGOING → CANCELLED
        """
        valid_transitions = {
            (EventStatus.PLANNED, EventStatus.ONGOING),
            (EventStatus.PLANNED, EventStatus.CANCELLED),
            (EventStatus.ONGOING, EventStatus.COMPLETED),
            (EventStatus.ONGOING, EventStatus.CANCELLED),
        }
        
        if current_status == new_status:
            return

        if (current_status, new_status) not in valid_transitions:
            raise BadRequestException(
                detail=f"Invalid status transition from {current_status} to {new_status}"
            )

    @staticmethod
    async def update_event(
        db: AsyncSession,
        event_id: uuid.UUID,
        update_data: EventUpdate,
        user: User
    ) -> TravelEvent:
        """
        Update an event. Only Creator or Group Admin can update.
        """
        # Fetch event with group to check permissions
        query = select(TravelEvent).options(
            selectinload(TravelEvent.group).selectinload(Group.members),
            selectinload(TravelEvent.participants)
        ).where(
            and_(
                TravelEvent.id == event_id,
                TravelEvent.deleted_at.is_(None)
            )
        )
        result = await db.execute(query)
        event = result.scalar_one_or_none()
        
        if not event:
            raise NotFoundException(detail="Event not found")

        # Check Permissions: Creator OR Group Admin
        is_creator = event.created_by == user.id
        
        # Check if user is group admin
        is_group_admin = False
        if not is_creator:
            # Check membership role
            member_query = select(GroupMember).where(
                and_(
                    GroupMember.group_id == event.group_id,
                    GroupMember.user_id == user.id,
                    GroupMember.role == GroupMemberRole.ADMIN,
                    GroupMember.left_at.is_(None)
                )
            )
            member_result = await db.execute(member_query)
            if member_result.scalar_one_or_none():
                is_group_admin = True
        
        if not (is_creator or is_group_admin):
            raise PermissionDeniedException(
                detail="Only the event creator or group admin can update this event"
            )

        # Apply Updates
        if update_data.status:
            EventService._validate_status_transition(event.status, update_data.status)
            event.status = update_data.status
        
        if update_data.name and update_data.name != event.name:
            # Check for name uniqueness in the group
            name_query = select(TravelEvent).where(
                and_(
                    TravelEvent.group_id == event.group_id,
                    TravelEvent.name == update_data.name,
                    TravelEvent.id != event.id,
                    TravelEvent.deleted_at.is_(None)
                )
            )
            name_result = await db.execute(name_query)
            if name_result.scalar_one_or_none():
                raise BadRequestException(
                    detail=f"Event with name '{update_data.name}' already exists in this group"
                )
            event.name = update_data.name

        if update_data.destination:
            event.destination = update_data.destination
        if update_data.start_time:
            event.start_time = update_data.start_time
        if update_data.end_time:
            event.end_time = update_data.end_time
            
        # Validate time range if both changed or one changed
        start = update_data.start_time or event.start_time
        end = update_data.end_time or event.end_time
        if end <= start:
             raise BadRequestException(detail="End time must be after start time")

        event.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(event)
        
        logger.info(f"Event {event.id} updated by user {user.id}. New Permission: {event.status}")
        
        # Trigger Notification if Cancelled
        if event.status == EventStatus.CANCELLED:
            # Notify all participants 
            # Fetch participants
            parts_query = select(EventParticipant).where(
                and_(
                    EventParticipant.event_id == event.id,
                    EventParticipant.status.in_([ParticipantStatus.ACCEPTED, ParticipantStatus.INVITED])
                )
            )
            parts_result = await db.execute(parts_query)
            participants = parts_result.scalars().all()
            
            receiver_ids = [p.user_id for p in participants if p.user_id != user.id]
            
            if receiver_ids:
                try:
                    await NotificationService.create_bulk_notifications(
                        db,
                        NotificationCreate(
                            type=NotificationType.EVENT_CANCELLED,
                            title=f"Event Cancelled: {event.name}",
                            message=f"Event '{event.name}' has been cancelled by {user.first_name}",
                            reference_type=ReferenceType.EVENT,
                            reference_id=event.id
                        ),
                        receiver_ids=receiver_ids,
                        tenant_id=event.tenant_id
                    )
                except Exception as e:
                    logger.error(f"Failed to send notifications for event cancel: {e}")

        return event

    # ==================== Participant Management Methods ====================

    @staticmethod
    async def list_participants(
        db: AsyncSession,
        event_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[Sequence[EventParticipant], int]:
        """
        List all participants for an event with pagination.
        """
        # Count total
        count_query = select(func.count()).select_from(EventParticipant).where(
            EventParticipant.event_id == event_id
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # List with pagination
        query = select(EventParticipant).options(
            selectinload(EventParticipant.user),
            selectinload(EventParticipant.event)
        ).where(
            EventParticipant.event_id == event_id
        ).order_by(EventParticipant.created_at.asc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        participants = result.scalars().all()
        
        logger.info(f"Listed {len(participants)} participants for event {event_id}")
        
        return participants, total
    
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
        
        # Lifecycle Check: Cannot accept if event is closed
        if participant.event.status in [EventStatus.COMPLETED, EventStatus.CANCELLED]:
             raise BadRequestException(detail="Cannot accept invitation for a completed or cancelled event")

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
        # Lifecycle Check: Cannot add if event is not PLANNED
        if event.status != EventStatus.PLANNED:
             raise BadRequestException(detail="Cannot add participants unless event is PLANNED")

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
        
        query = select(EventParticipant).options(
            selectinload(EventParticipant.user)
        ).where(EventParticipant.id == participant.id)
        result = await db.execute(query)
        participant = result.scalar_one()
        
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
        
        participant.status = ParticipantStatus.REMOVED
        participant.responded_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        logger.info(f"User {target_user_id} removed from event {event_id} by admin")
        
        try:
             await NotificationService.create_notification(
                db,
                NotificationCreate(
                    type=NotificationType.PARTICIPANT_REMOVED,
                    title=f"Removed from event",
                    message=f"You have been removed from event {event_id}",
                    reference_type=ReferenceType.EVENT,
                    reference_id=event_id
                ),
                receiver_id=target_user_id,
                tenant_id=participant.event.tenant_id
            )
        except Exception as e:
            logger.error(f"Failed to send notification for participant remove: {e}")

    @staticmethod
    async def delete_event(
        db: AsyncSession,
        event: TravelEvent
    ) -> None:
        """
        Soft delete an event.
        """
        event.soft_delete()
        await db.commit()
        logger.info(f"Event {event.id} soft deleted")


__all__ = ["EventService"]
