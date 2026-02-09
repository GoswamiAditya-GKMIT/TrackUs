"""
Authentication dependencies for route protection.
"""
import uuid

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.users.model import User
from app.core.security import decode_access_token
from app.core.exceptions import AuthenticationException

# Security scheme for Swagger UI - HTTPBearer for JWT tokens
security = HTTPBearer(
    scheme_name="Bearer",
    description="Enter your JWT access token"
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get the currently authenticated user from JWT token.
    """
    from app.modules.users.service import UserService
    from app.modules.auth.blacklist_service import TokenBlacklistService
    
    token = credentials.credentials
    
    payload = decode_access_token(token)
    if not payload:
        raise AuthenticationException(detail="Invalid or expired token")
    
    jti = payload.get("jti")
    if jti:
        is_blacklisted = await TokenBlacklistService.is_token_blacklisted(db, jti)
        if is_blacklisted:
            raise AuthenticationException(detail="Token has been revoked")
    
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationException(detail="Invalid token payload")
    
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise AuthenticationException(detail="Invalid user ID in token")
    
    user = await UserService.get_user(db, user_id)
    
    if not user.is_active:
        raise AuthenticationException(detail="User account is inactive")
    
    if not user.is_email_verified:
        raise AuthenticationException(detail="Email not verified")
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    return current_user


async def require_super_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require that the current user is a SUPER_ADMIN.
    """

    from app.core.permissions import (
        require_super_admin as core_require_super_admin
    )
    
    core_require_super_admin(current_user)
    return current_user


async def require_tenant_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require that the current user is a TENANT_ADMIN or SUPER_ADMIN.
    """
    
    from app.core.permissions import require_tenant_admin as core_require_tenant_admin
    
    core_require_tenant_admin(current_user)
    return current_user
