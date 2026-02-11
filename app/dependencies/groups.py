"""
Group-related dependencies for access control.
"""
import uuid
from typing import Sequence
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.users.model import User
from app.dependencies.auth import get_current_user
from app.modules.groups.service import GroupService, MembershipService
from app.modules.groups.model import Group, GroupMember
from app.common.enums import GroupMemberRole, UserRole
from app.core.exceptions import (
    PermissionDeniedException,
    NotFoundException
)


async def get_valid_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Group:
    """
    Dependency to fetch a group and verify it exists and belongs to the user's tenant.
    """
    return await GroupService.get_group(db, group_id, current_user)


async def get_current_membership(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    group: Group = Depends(get_valid_group)
) -> GroupMember:
    """
    Dependency to get the current user's membership in a group.
    Also ensures the group exists and belongs to the user's tenant.
    """
    membership = await MembershipService.get_membership(db, group.id, current_user.id)
    if not membership:
        raise PermissionDeniedException(detail="You are not a member of this group")
    return membership


async def require_group_admin(
    current_user: User = Depends(get_current_user),
    membership: GroupMember = Depends(get_current_membership)
) -> GroupMember:
    """
    Dependency to ensure the current user is an ADMIN of the group.
    Tenant Admins are NOT automatically group admins unless they are members with ADMIN role.
    """
    if membership.role != GroupMemberRole.ADMIN:
        raise PermissionDeniedException(detail="Group admin privileges required")
    return membership


async def require_group_member(
    membership: GroupMember = Depends(get_current_membership)
) -> GroupMember:
    """
    Dependency to ensure the current user is a member of the group.
    """
    return membership


async def require_group_manager(
    current_user: User = Depends(get_current_user),
    group: Group = Depends(get_valid_group),
    db: AsyncSession = Depends(get_db)
) -> tuple[Group, User]:
    """
    Dependency to allow either Group Admins or Tenant Admins to manage group settings.
    Returns (group, acting_user).
    """
    # Tenant Admin power
    if current_user.role == UserRole.TENANT_ADMIN and current_user.tenant_id == group.tenant_id:
        return group, current_user

    # Check group admin status
    membership = await MembershipService.get_membership(db, group.id, current_user.id)

    if not membership:
        raise PermissionDeniedException(detail="You are not a member of this group")

    if membership.role != GroupMemberRole.ADMIN:
        raise PermissionDeniedException(detail="Admin privileges required to perform this action")
    
    return group, current_user


async def require_group_access(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    group: Group = Depends(get_valid_group)
) -> Group:
    """
    Dependency to ensure the user has access to view a group's details.
    Tenant Admins have access to everything in their tenant.
    Regular users must be members of the group.
    """
    if current_user.role == UserRole.TENANT_ADMIN:
        return group

    membership = await MembershipService.get_membership(db, group.id, current_user.id)
    if not membership:
        raise PermissionDeniedException(detail="You do not have access to this group")
    
    return group


async def get_accessible_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Sequence[Group]:
    """
    Dependency to return a list of groups the current user is allowed to see.
    """
    if current_user.role == UserRole.TENANT_ADMIN:
        return await GroupService.list_tenant_groups(db, current_user.tenant_id)
    
    return await GroupService.list_user_groups(db, current_user)
