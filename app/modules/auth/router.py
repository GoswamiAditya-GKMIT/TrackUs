"""
Authentication router - HTTP endpoints for authentication.
"""
from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.rate_limiter import RateLimiter 

from app.db.session import get_db
from app.core.redis import get_redis
from app.modules.auth.schema import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    EmailVerificationRequest,
    ResendVerificationRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    LogoutRequest
)
from app.modules.auth.service import AuthService
from app.modules.users.model import User
from app.dependencies.auth import get_current_user, security
from app.common.response_utils import success_response
from app.common.responses import SuccessResponse
from fastapi import BackgroundTasks
from app.core.exceptions import AuthenticationException
from datetime import datetime, timezone
from app.core.security import decode_access_token, decode_refresh_token
from app.modules.auth.blacklist_service import TokenBlacklistService
from app.modules.users.service import UserService
from app.common.constants import (
    RATE_LIMIT_AUTH_TIMES,
    RATE_LIMIT_AUTH_SECONDS,
    RATE_LIMIT_REFRESH_TIMES
)


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/login",
    response_model=SuccessResponse[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="User login",
    dependencies=[Depends(RateLimiter(times=RATE_LIMIT_AUTH_TIMES, seconds=RATE_LIMIT_AUTH_SECONDS))]
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
    summary="Refresh access token",
    dependencies=[Depends(RateLimiter(times=RATE_LIMIT_REFRESH_TIMES, seconds=RATE_LIMIT_AUTH_SECONDS))]
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
    summary="Verify user email",
    dependencies=[Depends(RateLimiter(times=RATE_LIMIT_AUTH_TIMES, seconds=RATE_LIMIT_AUTH_SECONDS))]
)
async def verify_email(
    verification_data: EmailVerificationRequest,
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):

    user = await UserService.verify_user_email(db, redis_client, verification_data.token)
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
    "/email-verification/resend",
    response_model=SuccessResponse[dict],
    summary="Resend email verification link",
    dependencies=[Depends(RateLimiter(times=RATE_LIMIT_AUTH_TIMES, seconds=RATE_LIMIT_AUTH_SECONDS))]
)
async def resend_verification(
    resend_data: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    
    user, token = await UserService.resend_verification_email(db, resend_data.email)
    
    from app.modules.users.tasks import send_verification_email
    background_tasks.add_task(
        send_verification_email,
        email=user.email,
        first_name=user.first_name,
        token=token
    )
    
    return success_response(
        message="Verification email sent successfully.",
        data={
            "message": "Please check your email for the verification link."
        }
    )


@router.post(
    "/logout",
    response_model=SuccessResponse[dict],
    summary="Logout user"
)
async def logout(
    logout_data: LogoutRequest = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
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
    
    # Add access token to blacklist (Redis)
    await TokenBlacklistService.blacklist_token(
        db=db,
        jti=jti,
        user_id=current_user.id,
        token_type="access",
        expires_at=expires_at,
        reason="logout",
        redis_client=redis_client
    )
    
    # Also blacklist refresh token if provided (DB)
    if logout_data and logout_data.refresh_token:
        refresh_payload = decode_refresh_token(logout_data.refresh_token)
        if refresh_payload:
            r_jti = refresh_payload.get("jti")
            r_exp = refresh_payload.get("exp")
            if r_jti and r_exp:
                r_expires_at = datetime.fromtimestamp(r_exp, tz=timezone.utc)
                await TokenBlacklistService.blacklist_token(
                    db=db,
                    jti=r_jti,
                    user_id=current_user.id,
                    token_type="refresh",
                    expires_at=r_expires_at,
                    reason="logout"
                )
    
    return success_response(
        message="Logged out successfully",
        data={
            "message": "Your session has been terminated"
        }
    )


@router.post(
    "/forgot-password",
    response_model=SuccessResponse[dict],
    summary="Request password reset",
    dependencies=[Depends(RateLimiter(times=RATE_LIMIT_AUTH_TIMES, seconds=RATE_LIMIT_AUTH_SECONDS))]
)
async def forgot_password(
    request_data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Generates a token and sends an email with the reset link.
    """
    user = await UserService.get_user_by_email(db, request_data.email)
    
    if not user:
        # Return success even if email not found to prevent email enumeration
        return success_response(
            message="If the email exists, a password reset link has been sent.",
            data={"message": "Check your email inbox."}
        )

    if not user.is_active:
        # Optionally handle inactive users differently or just ignore
        return success_response(
            message="If the email exists, a password reset link has been sent.",
            data={"message": "Check your email inbox."}
        )
        
    # Generate reset token
    token = await AuthService.generate_and_store_token(
        redis_client, 
        user.email, 
        token_type=AuthService.PASSWORD_RESET_PREFIX
    )
    
    # Send email in background
    from app.modules.users.tasks import send_reset_password_email
    background_tasks.add_task(
        send_reset_password_email,
        email=user.email,
        first_name=user.first_name,
        token=token
    )
    
    return success_response(
        message="If the email exists, a password reset link has been sent.",
        data={"message": "Check your email inbox."}
    )


@router.post(
    "/reset-password",
    response_model=SuccessResponse[dict],
    summary="Reset password",
    dependencies=[Depends(RateLimiter(times=RATE_LIMIT_AUTH_TIMES, seconds=RATE_LIMIT_AUTH_SECONDS))]
)
async def reset_password(
    reset_data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Reset user password using a valid token.
    """
    await AuthService.reset_password(
        db, 
        redis_client, 
        reset_data.token, 
        reset_data.new_password
    )
    
    return success_response(
        message="Password has been reset successfully.",
        data={"message": "You can now login with your new password."}
    )
