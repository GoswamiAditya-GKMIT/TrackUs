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
    UserUpdate,
    UserResponse,
    UserListResponse,
    UserDetailResponse
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
    user, token = await UserService.create_user(db, user_data, current_user)
    
    from app.modules.users.tasks import send_verification_email
    background_tasks.add_task(
        send_verification_email,
        email=user.email,
        first_name=user.first_name,
        token=token
    )
    
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
    response_model=SuccessResponse[UserDetailResponse],
    summary="Get user by ID"
)
async def get_user(
    user: User = Depends(TargetUserValidator(action="access"))
):
    return success_response(
        message="User retrieved successfully",
        data=UserDetailResponse.model_validate(user)
    )


@router.get(
    "/",
    response_model=PaginatedResponse[UserListResponse],
    summary="List users"
)
async def list_users(
    pagination: PaginationParams = Depends(),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    deleted: Optional[bool] = Query(None, description="Filter by deleted status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    users, total = await UserService.list_users(
        db, current_user, pagination.skip, pagination.limit, is_active, deleted
    )
    
    return paginated_response(
        message="Users retrieved successfully",
        data=[UserListResponse.model_validate(u) for u in users],
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
        data=UserResponse.model_validate(updated_user)
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
