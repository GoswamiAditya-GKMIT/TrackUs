"""
Background tasks for user operations.
"""
import logging

from app.core.config import settings
from app.core.email import send_email, create_verification_email_body, create_reset_password_email_body

logger = logging.getLogger(__name__)


async def send_verification_email(
    email: str,
    first_name: str,
    token: str,
) -> None:

    try:
        verification_url = f"{settings.FRONTEND_URL}/email-verification/verify/{token}"
        
        body = create_verification_email_body(token, first_name, verification_url)
        
        # Send email
        await send_email(
            to_email=email,
            subject="Verify your TrackUs account",
            body=body
        )
        
        logger.info("Verification email sent")
    except Exception as e:
        logger.error(f"Failed to send verification email {str(e)}")


async def send_reset_password_email(
    email: str,
    first_name: str,
    token: str,
) -> None:

    try:
        reset_url = f"{settings.FRONTEND_URL}/auth/reset-password?token={token}"
        
        body = create_reset_password_email_body(token, first_name, reset_url)
        
        # Send email
        await send_email(
            to_email=email,
            subject="Reset your TrackUs password",
            body=body
        )
        
        logger.info("Password reset email sent")
    except Exception as e:
        logger.error(f"Failed to send password reset email {str(e)}")
