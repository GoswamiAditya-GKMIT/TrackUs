"""
Group router - HTTP endpoints for groups and memberships.
"""
import uuid
from typing import Sequence, Optional, Union

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.users.model import User
from app.modules.groups.model import Group, GroupMember
from app.dependencies.auth import get_current_user, require_tenant_admin, restrict_super_admin
from app.modules.groups.service import GroupService, MembershipService
from app.modules.groups.schema import (
    GroupCreate, 
    GroupUpdate, 
    GroupResponse, 
    GroupAdminResponse,
    GroupDetailResponse,
    GroupDetailAdminResponse,
    GroupMemberResponse,
    GroupMemberCreate,
    GroupMemberUpdate
)
from app.dependencies.groups import (
    get_valid_group,
    require_group_admin,
    require_group_member,
    require_group_manager,
    require_group_access,
    get_accessible_groups
)
from app.common.response_utils import success_response, paginated_response
from app.common.responses import SuccessResponse, PaginatedResponse
from app.dependencies.common import PaginationParams
from app.common.enums import UserRole

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post(
    "",
    response_model=SuccessResponse[GroupResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new group"
)
async def create_group(
    group_data: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    group = await GroupService.create_group(db, group_data, current_user)
    return success_response(
        message="Group created successfully",
        data=GroupResponse.model_validate(group)
    )


@router.get(
    "",
    response_model=PaginatedResponse[Union[GroupAdminResponse, GroupResponse]],
    summary="List groups",
    dependencies=[Depends(restrict_super_admin)]
)
async def list_groups(
    pagination: PaginationParams = Depends(),
    active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == UserRole.TENANT_ADMIN:
        groups, total = await GroupService.list_tenant_groups(
            db, current_user.tenant_id, pagination.skip, pagination.limit, active
        )
        data = [GroupAdminResponse.model_validate(g) for g in groups]
    else:
        # Regular users only see their active groups
        groups, total = await GroupService.list_user_groups(
            db, current_user, pagination.skip, pagination.limit
        )
        data = [GroupResponse.model_validate(g) for g in groups]
    
    response_data = paginated_response(
        message="Groups retrieved successfully",
        data=data,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )
    return JSONResponse(content=jsonable_encoder(response_data))


@router.get(
    "/{group_id}",
    response_model=SuccessResponse[Union[GroupDetailAdminResponse, GroupDetailResponse]],
    summary="Get group details"
)
async def get_group(
    group = Depends(require_group_access),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == UserRole.TENANT_ADMIN:
        data = GroupDetailAdminResponse.model_validate(group)
    else:
        data = GroupDetailResponse.model_validate(group)

    response_data = success_response(
        message="Group details retrieved successfully",
        data=data
    )
    return JSONResponse(content=jsonable_encoder(response_data))


@router.patch(
    "/{group_id}",
    response_model=SuccessResponse[GroupResponse],
    summary="Update group"
)
async def update_group(
    group_data: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    group_ctx: tuple[Group, User] = Depends(require_group_manager)
):
    group, user = group_ctx
    updated_group = await GroupService.update_group(db, group.id, group_data, user)
    return success_response(
        message="Group updated successfully",
        data=GroupResponse.model_validate(updated_group)
    )


@router.delete(
    "/{group_id}",
    response_model=SuccessResponse[dict],
    summary="Delete group"
)
async def delete_group(
    db: AsyncSession = Depends(get_db),
    group_ctx: tuple[Group, User] = Depends(require_group_manager)
):
    group, user = group_ctx
    await GroupService.delete_group(db, group.id, user)
    return success_response(
        message="Group deleted successfully",
        data={}
    )


# --- Membership Endpoints ---

@router.get(
    "/{group_id}/members",
    response_model=PaginatedResponse[GroupMemberResponse],
    summary="List group members",
    dependencies=[Depends(restrict_super_admin)]
)
async def list_members(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    membership: GroupMember = Depends(require_group_member)
):
    members, total = await MembershipService.list_members(
        db, membership.group_id, pagination.skip, pagination.limit
    )
    return paginated_response(
        message="Members retrieved successfully",
        data=[GroupMemberResponse.model_validate(m) for m in members],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )


@router.post(
    "/{group_id}/members",
    response_model=SuccessResponse[GroupMemberResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add member to group"
)
async def add_member(
    member_data: GroupMemberCreate,
    db: AsyncSession = Depends(get_db),
    membership: GroupMember = Depends(require_group_admin)
):
    membership = await MembershipService.add_member(
        db, 
        membership.group_id, 
        member_data, 
        membership.user
    )
    return success_response(
        message="Member added successfully",
        data=GroupMemberResponse.model_validate(membership)
    )


@router.patch(
    "/{group_id}/members/{user_id}",
    response_model=SuccessResponse[GroupMemberResponse],
    summary="Update member role"
)
async def update_member_role(
    user_id: uuid.UUID,
    update_data: GroupMemberUpdate,
    db: AsyncSession = Depends(get_db),
    membership: GroupMember = Depends(require_group_admin)
):
    membership = await MembershipService.promote_demote(
        db, 
        membership.group_id, 
        user_id, 
        update_data, 
        membership.user
    )
    return success_response(
        message="Member role updated successfully",
        data=GroupMemberResponse.model_validate(membership)
    )


@router.delete(
    "/{group_id}/members/{user_id}",
    response_model=SuccessResponse[dict],
    summary="Remove member from group"
)
async def remove_member(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    membership: GroupMember = Depends(require_group_admin)
):
    await MembershipService.remove_member(
        db, 
        membership.group_id, 
        user_id, 
        membership.user
    )
    return success_response(
        message="Member removed successfully",
        data={}
    )


@router.post(
    "/{group_id}/leave",
    response_model=SuccessResponse[dict],
    summary="Leave group"
)
async def leave_group(
    db: AsyncSession = Depends(get_db),
    membership: GroupMember = Depends(require_group_member)
):
    await MembershipService.leave_group(db, membership.group_id, membership.user)
    return success_response(
        message="You have left the group",
        data={}
    )
