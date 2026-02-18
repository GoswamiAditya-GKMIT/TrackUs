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
from app.modules.users.schema import UserResponse
from app.modules.auth.service import AuthService
from app.modules.users.model import User
from app.dependencies.auth import get_current_user, security
from app.common.response_utils import success_response
from app.common.responses import SuccessResponse
from fastapi import BackgroundTasks
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
    response_model=SuccessResponse[UserResponse],
    summary="Verify user email",
    dependencies=[Depends(RateLimiter(times=RATE_LIMIT_AUTH_TIMES, seconds=RATE_LIMIT_AUTH_SECONDS))]
)
async def verify_email(
    verification_data: EmailVerificationRequest,
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):

    user = await AuthService.verify_email(db, redis_client, verification_data.token)
    return success_response(
        message="Email verified successfully. You can login now.",
        data=user
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
    
    user, token = await AuthService.resend_verification_email(db, resend_data.email)
    
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
    await AuthService.logout(
        db=db,
        redis_client=redis_client,
        current_user=current_user,
        access_token=credentials.credentials,
        refresh_token=logout_data.refresh_token if logout_data else None
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
    """
    Generates a token and sends an email with the reset link.
    """
    user, token = await AuthService.forgot_password(db, redis_client, request_data.email)
    
    if user and token:
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
