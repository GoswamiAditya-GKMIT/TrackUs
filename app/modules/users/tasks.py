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
    base_url: str = "http://localhost:3000"
) -> None:

    try:
        token = generate_verification_token(email)
        
        verification_url = f"{base_url}/email-verification/verify/{token}"
        
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
