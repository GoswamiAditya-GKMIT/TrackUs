"""
Background tasks for user operations.
"""
import logging

from app.core.email import (
    generate_verification_token,
    send_email,
    create_verification_email_body
)

logger = logging.getLogger(__name__)


async def send_verification_email(
    email: str,
    first_name: str,
    base_url: str = "http://localhost:8000"
) -> None:

    try:
        token = generate_verification_token(email)
        
        verification_url = f"{base_url}/api/v1/auth/email-verification/verify?token={token}"
        
        body = create_verification_email_body(verification_url, first_name)
        
        # Send email
        await send_email(
            to_email=email,
            subject="Verify your TrackUs account",
            body=body
        )
        
        logger.info("Verification email sent")
    except Exception as e:
        logger.error(f"Failed to send verification email {str(e)}")
