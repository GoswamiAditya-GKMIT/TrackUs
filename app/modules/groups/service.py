"""
Group and Membership service layer.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Sequence
import uuid

from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.groups.model import Group, GroupMember
from app.modules.groups.schema import GroupCreate, GroupUpdate, GroupMemberCreate, GroupMemberUpdate
from app.modules.users.model import User
from app.common.enums import GroupMemberRole, UserRole
from app.realtime.manager import manager
from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
    PermissionDeniedException,
    TenantIsolationException
)
from app.modules.notifications.service import NotificationService
from app.modules.notifications.schema import NotificationCreate
from app.common.constants import NotificationType, ReferenceType
        

logger = logging.getLogger(__name__)


class GroupService:
    """Service for managing Group lifecycle and memberships."""

    @staticmethod
    async def create_group(
        db: AsyncSession,
        group_data: GroupCreate,
        creator: User
    ) -> Group:
        """
        Create a new group and add the creator as its first ADMIN.
        """
        if not creator.tenant_id:
            raise BadRequestException(detail="Users must belong to a tenant to create groups")

        # Check name uniqueness
        await GroupService._check_name_uniqueness(db, creator.tenant_id, group_data.name)

        group = Group(
            name=group_data.name,
            description=group_data.description,
            tenant_id=creator.tenant_id,
            created_by=creator.id,
            is_active=True
        )
        db.add(group)
        await db.flush()  # Get group ID

        # Create initial membership for creator
        membership = GroupMember(
            group_id=group.id,
            user_id=creator.id,
            role=GroupMemberRole.ADMIN
        )
        db.add(membership)
        
        await db.commit()
        await db.refresh(group)
        logger.info(f"Group '{group.name}' created by user {creator.id}")
        return group

    @staticmethod
    async def get_group(
        db: AsyncSession,
        group_id: uuid.UUID,
        user: User
    ) -> Group:
        """
        Fetch a group and verify tenant isolation.
        """
        query = select(Group).where(
            and_(
                Group.id == group_id,
                Group.deleted_at == None
            )
        )
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if not group:
            raise NotFoundException(detail="Group not found")

        # Tenant isolation
        if group.tenant_id != user.tenant_id:
            raise TenantIsolationException()

        # Count members
        count_query = select(func.count()).select_from(GroupMember).where(
            and_(
                GroupMember.group_id == group_id,
                GroupMember.left_at.is_(None)
            )
        )
        member_count = (await db.execute(count_query)).scalar()
        group.member_count = member_count

        return group

    @staticmethod
    async def list_user_groups(
        db: AsyncSession,
        user: User,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[Sequence[Group], int]:
        """
        List all groups where the user is a member.
        """
        base_query = select(Group).join(GroupMember).where(
            and_(
                GroupMember.user_id == user.id,
                GroupMember.left_at == None,
                Group.deleted_at == None
            )
        )
        
        # Count
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Data
        query = base_query.offset(skip).limit(limit).order_by(Group.created_at.desc())
        result = await db.execute(query)
        groups = result.scalars().all()
        
        # Populate member counts
        for group in groups:
            count_query = select(func.count()).select_from(GroupMember).where(
                and_(
                    GroupMember.group_id == group.id,
                    GroupMember.left_at.is_(None)
                )
            )
            group.member_count = (await db.execute(count_query)).scalar()
            
        return groups, total

    @staticmethod
    async def list_tenant_groups(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        active: Optional[bool] = None
    ) -> tuple[Sequence[Group], int]:
        """
        List all groups in a tenant (for admins).
        """
        base_query = select(Group).where(
            Group.tenant_id == tenant_id
        )
        
        if active is True:
            base_query = base_query.where(Group.deleted_at.is_(None))
        elif active is False:
            base_query = base_query.where(Group.deleted_at.is_not(None))
        # If active is None, return all (no filter on deleted_at)

        # Count
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Data
        query = base_query.offset(skip).limit(limit).order_by(Group.created_at.desc())
        result = await db.execute(query)
        groups = result.scalars().all()
        
        for group in groups:
            count_query = select(func.count()).select_from(GroupMember).where(
                and_(
                    GroupMember.group_id == group.id,
                    GroupMember.left_at.is_(None)
                )
            )
            group.member_count = (await db.execute(count_query)).scalar()

        return groups, total

    @staticmethod
    async def update_group(
        db: AsyncSession,
        group_id: uuid.UUID,
        group_data: GroupUpdate,
        user: User
    ) -> Group:
        """
        Update group metadata. Only group admins or tenant admins can update.
        Note: Verification of admin status is done in Router/Dependencies.
        """
        group = await GroupService.get_group(db, group_id, user)
        
        update_data = group_data.model_dump(exclude_unset=True)
        
        # Check name uniqueness if name is changing
        if "name" in update_data and update_data["name"] != group.name:
            await GroupService._check_name_uniqueness(db, user.tenant_id, update_data["name"])

        for key, value in update_data.items():
            setattr(group, key, value)
        
        await db.commit()
        await db.refresh(group)
        logger.info(f"Group {group_id} updated by user {user.id}")
        return group

    @staticmethod
    async def delete_group(
        db: AsyncSession,
        group_id: uuid.UUID,
        user: User
    ) -> None:
        """
        Soft delete a group.
        """
        group = await GroupService.get_group(db, group_id, user)
        group.soft_delete()
        
        await db.execute(
            update(GroupMember)
            .where(GroupMember.group_id == group_id, GroupMember.left_at.is_(None))
            .values(left_at=datetime.now(timezone.utc))
        )
        
        from app.modules.events.model import TravelEvent
        await db.execute(
            update(TravelEvent)
            .where(TravelEvent.group_id == group_id, TravelEvent.deleted_at.is_(None))
            .values(deleted_at=datetime.now(timezone.utc))
        )
     
        
        from app.modules.events.model import EventParticipant
        from app.common.enums import ParticipantStatus
        
        event_ids_query = select(TravelEvent.id).where(TravelEvent.group_id == group_id)
        event_ids_result = await db.execute(event_ids_query)
        event_ids = [r for r in event_ids_result.scalars().all()]
        
        if event_ids:
            await db.execute(
                update(EventParticipant)
                .where(EventParticipant.event_id.in_(event_ids), EventParticipant.status != ParticipantStatus.LEFT)
                .values(status=ParticipantStatus.LEFT, responded_at=datetime.now(timezone.utc))
            )
        
        await db.commit()
        logger.info(f"Group {group_id} soft-deleted by user {user.id}")

    @staticmethod
    async def _check_name_uniqueness(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        name: str
    ) -> None:
        """
        Check if an active group with the same name already exists in the tenant.
        """
        query = select(Group).where(
            and_(
                Group.tenant_id == tenant_id,
                Group.name == name,
                Group.deleted_at == None
            )
        )
        result = await db.execute(query)
        if result.scalars().first():
            raise BadRequestException(detail=f"Group with name '{name}' already exists in your organization")


class MembershipService:
    """Service for managing group memberships and roles."""

    @staticmethod
    async def get_membership(
        db: AsyncSession,
        group_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Optional[GroupMember]:
        """
        Fetch membership record.
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

    @staticmethod
    async def list_members(
        db: AsyncSession,
        group_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[Sequence[GroupMember], int]:
        """
        List all active members of a group.
        """
        base_query = select(GroupMember).where(
            and_(
                GroupMember.group_id == group_id,
                GroupMember.left_at == None
            )
        ).options(selectinload(GroupMember.user))

        # Count
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Data
        query = base_query.offset(skip).limit(limit).order_by(GroupMember.created_at.asc())
        result = await db.execute(query)
        return result.scalars().all(), total

    @staticmethod
    async def add_member(
        db: AsyncSession,
        group_id: uuid.UUID,
        member_data: GroupMemberCreate,
        requester: User
    ) -> GroupMember:
        """
        Add a new member to the group.
        """
        # Ensure target user exists and belongs to the same tenant
        from app.modules.users.service import UserService
        target_user = await UserService.get_user(db, member_data.user_id)
        
        if target_user.tenant_id != requester.tenant_id:
            raise PermissionDeniedException(detail="Cannot add users from other tenants")
        
        # Check if a membership record already exists (even if they previously left)
        # We query directly to avoid the 'left_at is None' filter in get_membership
        query = select(GroupMember).where(
            and_(
                GroupMember.group_id == group_id,
                GroupMember.user_id == member_data.user_id
            )
        )
        result = await db.execute(query)
        membership = result.scalar_one_or_none()

        if membership:
            if membership.left_at is None:
                raise BadRequestException(detail="User is already a member of this group")
            
            # Reactivate membership
            logger.info(f"Reactivating membership for user {member_data.user_id} in group {group_id}")
            membership.left_at = None
            membership.role = member_data.role
        else:
            # Create new membership
            membership = GroupMember(
                group_id=group_id,
                user_id=member_data.user_id,
                role=member_data.role
            )
            db.add(membership)
        
        await db.commit()
        await db.refresh(membership)
        

        try:
            await NotificationService.create_notification(
                db,
                NotificationCreate(
                    type=NotificationType.GROUP_ADDED, 
                    title=f"Added to group {group_id}",
                    message=f"You have been added to a group by user {requester.first_name}",
                    reference_type=ReferenceType.GROUP,
                    reference_id=group_id
                ),
                receiver_id=member_data.user_id,
                tenant_id=requester.tenant_id
            )
        except Exception as e:
            logger.error(f"Failed to send notification for group add: {e}")

        logger.info(f"User {member_data.user_id} added/reactivated in group {group_id} by {requester.id}")
        return membership

    @staticmethod
    async def remove_member(
        db: AsyncSession,
        group_id: uuid.UUID,
        user_id: uuid.UUID,
        requester: User
    ) -> None:
        """
        Remove a member from the group.
        """
        membership = await MembershipService.get_membership(db, group_id, user_id)
        if not membership:
            raise NotFoundException(detail="Membership not found")

        # If removing an admin, check if they are the last one
        if membership.role == GroupMemberRole.ADMIN:
            await MembershipService._ensure_not_last_admin(db, group_id)

        membership.left_at = datetime.now(timezone.utc)
        await db.commit()
        
        # Proactively disconnect from chat if connected
        await manager.disconnect_user(str(group_id), str(user_id))
        
        logger.info(f"User {user_id} removed from group {group_id} by {requester.id}")

    @staticmethod
    async def leave_group(
        db: AsyncSession,
        group_id: uuid.UUID,
        user: User
    ) -> None:
        """
        Current user leaves the group.
        """
        membership = await MembershipService.get_membership(db, group_id, user.id)
        if not membership:
            raise BadRequestException(detail="You are not a member of this group")

        # Check if last admin
        if membership.role == GroupMemberRole.ADMIN:
            await MembershipService._ensure_not_last_admin(db, group_id)

        membership.left_at = datetime.now(timezone.utc)
        await db.commit()
        
        # Proactively disconnect from chat if connected
        await manager.disconnect_user(str(group_id), str(user.id))
        
        logger.info(f"User {user.id} left group {group_id}")

    @staticmethod
    async def promote_demote(
        db: AsyncSession,
        group_id: uuid.UUID,
        user_id: uuid.UUID,
        update_data: GroupMemberUpdate,
        requester: User
    ) -> GroupMember:
        """
        Update member role (ADMIN <-> MEMBER).
        """
        membership = await MembershipService.get_membership(db, group_id, user_id)
        if not membership:
            raise NotFoundException(detail="Membership not found")

        # If demoting from ADMIN to MEMBER, check if last admin
        if membership.role == GroupMemberRole.ADMIN and update_data.role == GroupMemberRole.MEMBER:
            await MembershipService._ensure_not_last_admin(db, group_id)

        membership.role = update_data.role
        await db.commit()
        await db.refresh(membership)
        logger.info(f"User {user_id} role updated to {update_data.role} in group {group_id}")
        return membership

    @staticmethod
    async def _ensure_not_last_admin(db: AsyncSession, group_id: uuid.UUID) -> None:
        """
        Helper to check if a group has more than one admin.
        """
        query = select(func.count()).where(
            and_(
                GroupMember.group_id == group_id,
                GroupMember.role == GroupMemberRole.ADMIN,
                GroupMember.left_at == None
            )
        )
        result = await db.execute(query)
        admin_count = result.scalar()

        if admin_count <= 1:
            raise BadRequestException(detail="Cannot remove or demote the last admin of the group")
