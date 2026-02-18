"""
Group router - HTTP endpoints for groups and memberships.
"""
import uuid
from typing import Sequence, Optional, Union

from fastapi import APIRouter, Depends, status, Response
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
    data, total = await GroupService.list_groups_for_user(
        db, current_user, pagination.skip, pagination.limit, active
    )
    
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
    response_model=SuccessResponse[dict],
    summary="Get group details"
)
async def get_group(
    group = Depends(require_group_access),
    current_user: User = Depends(get_current_user)
):
    data = GroupService.get_group_details_for_user(current_user, group)

    return success_response(
        message="Group details retrieved successfully",
        data=data
    )


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
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete group"
)
async def delete_group(
    db: AsyncSession = Depends(get_db),
    group_ctx: tuple[Group, User] = Depends(require_group_manager)
):
    group, user = group_ctx
    await GroupService.delete_group(db, group.id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    group: Group = Depends(require_group_access)
):
    members, total = await MembershipService.list_members(
        db, group.id, pagination.skip, pagination.limit
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
    group_ctx: tuple[Group, User] = Depends(require_group_manager)
):
    group, acting_user = group_ctx
    membership = await MembershipService.add_member(
        db, 
        group.id, 
        member_data, 
        acting_user
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
    group_ctx: tuple[Group, User] = Depends(require_group_manager)
):
    group, acting_user = group_ctx
    membership = await MembershipService.promote_demote(
        db, 
        group.id, 
        user_id, 
        update_data, 
        acting_user
    )
    return success_response(
        message="Member role updated successfully",
        data=GroupMemberResponse.model_validate(membership)
    )


@router.delete(
    "/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member from group"
)
async def remove_member(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    group_ctx: tuple[Group, User] = Depends(require_group_manager)
):
    group, acting_user = group_ctx
    await MembershipService.remove_member(
        db, 
        group.id, 
        user_id, 
        acting_user
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
