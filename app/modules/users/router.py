"""
User router - HTTP endpoints for user operations.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.redis import get_redis
from app.modules.users.schema import (
    UserCreate,
    UserUpdate
)
from app.modules.users.service import UserService
from app.modules.users.model import User
from app.dependencies.auth import get_current_user, require_admin
from app.dependencies.users import (
    TargetUserValidator
)
from app.common.enums import UserRole
from app.core.exceptions import PermissionDeniedException
from app.common.response_utils import success_response, paginated_response
from app.common.responses import SuccessResponse, PaginatedResponse
from app.modules.users.schema import UserResponse
from fastapi import Response
from app.dependencies.common import PaginationParams



router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/",
    response_model=SuccessResponse[None],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user"
)
async def create_user(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):  
    await UserService.create_user(db, user_data, current_user, background_tasks)
    return success_response(
        message="User created successfully. Verification link sent to email.",
        data=None
    )


@router.get(
    "/me",
    response_model=SuccessResponse[UserResponse],
    summary="Get current user"
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get information about the currently authenticated user.
    """
    from app.modules.auth.schema import CurrentUser
    
    user_data = CurrentUser.model_validate(current_user)
    return success_response(
        message="User information retrieved successfully",
        data=user_data.model_dump()
    )


@router.get(
    "/{user_id}",
    response_model=SuccessResponse[UserResponse],
    summary="Get user by ID"
)
async def get_user(
    user: User = Depends(TargetUserValidator(action="access"))
):
    return success_response(
        message="User retrieved successfully",
        data={
            "id": str(user.id),
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role.value,
            "is_active": user.is_active,
            "is_email_verified": user.is_email_verified,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None
        }
    )



@router.get(
    "/",
    response_model=PaginatedResponse[UserResponse],
    summary="List users"
)
async def list_users(
    pagination: PaginationParams = Depends(),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    deleted: Optional[bool] = Query(None, description="Filter by deleted status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    users, total = await UserService.list_users(
        db, current_user, pagination.skip, pagination.limit, is_active, deleted
    )
    
    return paginated_response(
        message="Users retrieved successfully",
        data=[
            {
                "id": str(u.id),
                "tenant_id": str(u.tenant_id) if u.tenant_id else None,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "role": u.role.value,
                "is_active": u.is_active,
                "is_email_verified": u.is_email_verified,
                "created_at": u.created_at.isoformat(),
                "created_at": u.created_at.isoformat(),
                "updated_at": u.updated_at.isoformat() if u.updated_at else None,
                "deleted_at": u.deleted_at.isoformat() if u.deleted_at else None
            }
            for u in users
        ],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )


@router.patch(
    "/{user_id}",
    response_model=SuccessResponse[UserResponse],
    summary="Update a user"
)
async def update_user(
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(TargetUserValidator(action="update")),
    current_user: User = Depends(get_current_user)
):
    updated_user = await UserService.update_user(db, user, user_data, current_user)
    
    return success_response(
        message="User updated successfully",
        data={
            "id": str(updated_user.id),
            "tenant_id": str(updated_user.tenant_id) if updated_user.tenant_id else None,
            "email": updated_user.email,
            "first_name": updated_user.first_name,
            "last_name": updated_user.last_name,
            "role": updated_user.role.value,
            "is_active": updated_user.is_active,
            "is_email_verified": updated_user.is_email_verified,
            "created_at": updated_user.created_at.isoformat(),
            "created_at": updated_user.created_at.isoformat(),
            "updated_at": updated_user.updated_at.isoformat(),
            "deleted_at": updated_user.deleted_at.isoformat() if updated_user.deleted_at else None
        }
    )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user"
)
async def delete_user(
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis),
    user: User = Depends(TargetUserValidator(action="delete")),
    current_user: User = Depends(get_current_user)
):
    await UserService.delete_user(db, redis_client, user, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
