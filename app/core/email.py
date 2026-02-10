"""
Email utilities for sending verification emails and managing tokens.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import aiosmtplib
from email.message import EmailMessage

from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)


def generate_verification_token(email: str) -> str:
    """
    Generate a JWT token for email verification.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
    )
    to_encode = {
        "sub": email,
        "exp": expire,
        "type": "email_verification"
    }
    token = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return token


def verify_email_token(token: str) -> Optional[str]:

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "email_verification":
            return None
        email: str = payload.get("sub")
        return email
    except JWTError:
        return None



async def send_email(
    to_email: str,
    subject: str,
    body: str
) -> None:
    message = EmailMessage()
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    try:
        # Log masked email for privacy
        masked_email = f"{to_email[:3]}...@{to_email.split('@')[1]}" if "@" in to_email else "unknown"
        logger.info(f"Sending email to {masked_email} via {settings.SMTP_HOST}...")
        
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_TLS,
        )
        logger.info(f"Email sent successfully to {masked_email}")
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")


def create_verification_email_body(token: str, user_name: str, verification_url: str) -> str:

    return f"""
        Hello {user_name},

        Welcome to TrackUs! Please verify your email address using the verification link below:

        
        {verification_url}
        

        This link will expire in {settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS} hours.

        If you didn't create an account with TrackUs, please ignore this email.

        Best regards,
        The TrackUs Team
        """
