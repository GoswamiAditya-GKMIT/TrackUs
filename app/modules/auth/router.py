"""
Authentication router - HTTP endpoints for authentication.
"""
from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.schema import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest
)
from app.modules.auth.service import AuthService
from app.modules.users.model import User
from app.dependencies.auth import get_current_user, security
from app.common.response_utils import success_response
from app.common.responses import SuccessResponse
from app.core.exceptions import AuthenticationException
from datetime import datetime, timezone
from app.core.security import decode_access_token
from app.modules.auth.blacklist_service import TokenBlacklistService
from app.modules.users.service import UserService


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/login",
    response_model=SuccessResponse[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="User login"
)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    token_response = await AuthService.login(db, login_data)
    return success_response(
        message="Login successful",
        data={
            "access_token": token_response.access_token,
            "refresh_token": token_response.refresh_token,
        }
    )


@router.post(
    "/refresh",
    response_model=SuccessResponse[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Refresh access token"
)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):

    token_response = await AuthService.refresh_access_token(db, refresh_data.refresh_token)
    return success_response(
        message="Token refreshed successfully",
        data={
            "access_token": token_response.access_token,
            "refresh_token": token_response.refresh_token,
        }
    )


@router.post(
    "/email-verification/verify",
    response_model=SuccessResponse[dict],
    summary="Verify user email"
)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
):

    user = await UserService.verify_user_email(db, token)
    return success_response(
        message="Email verified successfully. You can login now.",
        data={
            "id": str(user.id),
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role.value,
            "is_active": user.is_active,
            "is_email_verified": user.is_email_verified,
            "created_at": user.created_at.isoformat()
        }
    )


@router.post(
    "/logout",
    response_model=SuccessResponse[dict],
    summary="Logout user"
)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload:
        raise AuthenticationException(detail="Invalid token")
    
    jti = payload.get("jti")
    exp = payload.get("exp")
    
    if not jti:
        raise AuthenticationException(detail="Token does not have JTI")
    
    # Convert exp timestamp to datetime
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    
    # Add token to blacklist
    await TokenBlacklistService.blacklist_token(
        db=db,
        jti=jti,
        user_id=current_user.id,
        token_type="access",
        expires_at=expires_at,
        reason="logout"
    )
    
    return success_response(
        message="Logged out successfully",
        data={
            "message": "Your session has been terminated"
        }
    )
