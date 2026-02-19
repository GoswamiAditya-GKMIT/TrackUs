"""
Authentication dependencies for route protection.
"""
import uuid

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.redis import get_redis
from app.modules.users.model import User
from app.modules.auth.blacklist_service import TokenBlacklistService
from app.core.security import decode_access_token
from app.core.exceptions import (
    AuthenticationException,
    PermissionDeniedException,
    NotFoundException
)
from app.common.enums import UserRole


# Security scheme for Swagger UI - HTTPBearer for JWT tokens
security = HTTPBearer(
    scheme_name="Bearer",
    description="Enter your JWT access token",
    auto_error = False
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
) -> User:
    """
    Get the currently authenticated user from JWT token.
    """
    from app.modules.users.service import UserService

    if not credentials:
        raise AuthenticationException(detail="No token provided")

    token = credentials.credentials
    
    payload = decode_access_token(token)
    if not payload:
        raise AuthenticationException(detail="Invalid or expired token")
    
    jti = payload.get("jti")
    if jti:
        is_blacklisted = await TokenBlacklistService.is_token_blacklisted(
            db, 
            jti, 
            token_type="access", 
            redis_client=redis_client
        )
        if is_blacklisted:
            raise AuthenticationException(detail="Token has been revoked")
    
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationException(detail="Invalid token payload")
    
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise AuthenticationException(detail="Invalid user ID in token")
    
    try:
        user = await UserService.get_user(db, user_id)
    except NotFoundException:
        raise PermissionDeniedException(detail="User not found or account deleted")
    
    if not user.is_active:
        raise AuthenticationException(detail="User account is inactive")
    
    if not user.is_email_verified:
        raise AuthenticationException(detail="Email not verified")
    
    return user


async def require_super_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require that the current user is a SUPER_ADMIN.
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise PermissionDeniedException(
            detail="Only super admins can perform this action"
        )
    return current_user


async def require_tenant_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require that the current user is a TENANT_ADMIN.
    """
    if current_user.role != UserRole.TENANT_ADMIN:
        raise PermissionDeniedException(
            detail="Only tenant admins can perform this action"
        )
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require that the current user is either a SUPER_ADMIN or TENANT_ADMIN.
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.TENANT_ADMIN]:
        raise PermissionDeniedException(
            detail="Only admins can perform this action"
        )
    return current_user

async def restrict_super_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Explicitly deny access to SUPER_ADMIN users.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        raise PermissionDeniedException(
            detail="Super admins are not allowed to perform this action"
        )
    return current_user
