import uuid

from fastapi import Depends
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.modules.users.model import User
from app.modules.events.model import TravelEvent
from app.modules.groups.model import GroupMember
from app.core.exceptions import NotFoundException, PermissionDeniedException
from app.common.enums import GroupMemberRole


async def _get_group_member(
    db: AsyncSession,
    group_id: uuid.UUID,
    user_id: uuid.UUID
) -> GroupMember | None:
    """
    Helper to get a user's group membership.
    
    Returns:
        GroupMember if user is an active member, None otherwise
    """
    query = select(GroupMember).where(
        and_(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
            GroupMember.left_at.is_(None)
        )
    )
    
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_accessible_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> TravelEvent:
    """
    Get event and verify user has access (is a member of the event's group).
    """
    # Fetch event with group
    query = select(TravelEvent).options(
        selectinload(TravelEvent.group),
        selectinload(TravelEvent.creator)
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
    
    if current_user.tenant_id and event.tenant_id != current_user.tenant_id:
        raise NotFoundException(detail="Event not found")
    
    # Check if user is a member of the event's group
    member = await _get_group_member(db, event.group_id, current_user.id)
    
    if not member:
        raise PermissionDeniedException(detail="You are not a member of this event's group")
    
    return event


async def require_event_admin(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> TravelEvent:
    """
    Verify user is event admin (group admin or event creator).
    """
    query = select(TravelEvent).options(
        selectinload(TravelEvent.group),
        selectinload(TravelEvent.creator)
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
    
    if current_user.tenant_id and event.tenant_id != current_user.tenant_id:
        raise NotFoundException(detail="Event not found")
    
    member = await _get_group_member(db, event.group_id, current_user.id)
    
    if not member:
        raise PermissionDeniedException(detail="You are not a member of this event's group")
    
    # Check if user is event creator or group admin
    if event.created_by == current_user.id or member.role == GroupMemberRole.ADMIN:
        return event
    
    raise PermissionDeniedException(
        detail="Only group admins or event creator can perform this action"
    )
