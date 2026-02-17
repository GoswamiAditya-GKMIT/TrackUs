"""
Authentication service layer - business logic for authentication.
"""
import logging
import secrets
import base64
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.modules.users.model import User
from app.modules.users.service import UserService
from app.modules.auth.schema import LoginRequest, TokenResponse
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token
)
from app.core.exceptions import AuthenticationException, EmailNotVerifiedException
from app.core.config import settings
import uuid
from app.modules.auth.blacklist_service import TokenBlacklistService



logger = logging.getLogger(__name__)


class AuthService:
    """Service class for authentication operations."""
    
    # Verification token constants
    TOKEN_PREFIX = "email_verification"
    EMAIL_VERIFICATION_PREFIX = "email_verification"
    PASSWORD_RESET_PREFIX = "password_reset"
    TOKEN_LENGTH = 32  # 32 bytes = 64 hex characters
    
    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        email: str,
        password: str
    ) -> User:

        user = await UserService.get_user_by_email(db, email)
        
        if not user:
            raise AuthenticationException(detail="Invalid email or password")
        
        if not verify_password(password, user.password):
            raise AuthenticationException(detail="Invalid email or password")
        
        if not user.is_active:
            raise AuthenticationException(detail="User account is inactive")
        
        if not user.is_email_verified:
            raise EmailNotVerifiedException()
        
        return user
    
    @staticmethod
    async def login(
        db: AsyncSession,
        login_data: LoginRequest
    ) -> TokenResponse:

        user = await AuthService.authenticate_user(
            db,
            login_data.email,
            login_data.password
        )
        
        token_data = {
            "sub": str(user.id),
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "role": user.role.value
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token
        )
    
    @staticmethod
    async def refresh_access_token(
        db: AsyncSession,
        refresh_token: str
    ) -> TokenResponse:

        payload = decode_refresh_token(refresh_token)
        
        if not payload:
            raise AuthenticationException(detail="Invalid or expired refresh token")
        
        user_id = payload.get("sub")
        jti = payload.get("jti")
        
        if not user_id or not jti:
            raise AuthenticationException(detail="Invalid token payload")
        
        # Check if refresh token is blacklisted
        if await TokenBlacklistService.is_token_blacklisted(db, jti):
            raise AuthenticationException(detail="Refresh token has been revoked")
        
        user = await UserService.get_user(db, uuid.UUID(user_id))
        
        if not user.is_active or not user.is_email_verified:
            raise AuthenticationException(detail="User account is inactive")
        
        token_data = {
            "sub": str(user.id),
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "role": user.role.value
        }
        
        access_token = create_access_token(token_data)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token  
        )
    
    # Email Verification Token Methods
    
    @staticmethod
    def _get_redis_key(email: str, token_type: str = "email_verification") -> str:
        """Generate Redis key for token."""
        return f"{token_type}:{email}"
    
    @staticmethod
    def _generate_token() -> str:
        """Generate a cryptographically secure random token."""
        return secrets.token_urlsafe(AuthService.TOKEN_LENGTH)
    
    @staticmethod
    async def generate_and_store_token(
        redis_client: redis.Redis, 
        email: str, 
        token_type: str = "email_verification"
    ) -> str:
        """
        Generate a new verification token for the email and store it in Redis.
        The returned token is a composite of base64(email) + . + random_secret.
        """
        # Determine TTL based on type
        if token_type == AuthService.PASSWORD_RESET_PREFIX:
            ttl_seconds = settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS * 3600
        else:
            ttl_seconds = settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS * 3600

        # Validate cooldown
        cooldown_key = f"{token_type}_cooldown:{email}"
        if await redis_client.get(cooldown_key):
            from app.core.exceptions import RateLimitException
            raise RateLimitException(
                detail=f"Please wait {settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS} seconds before requesting another email."
            )

        secret_token = AuthService._generate_token()
        
        # Store in Redis with TTL
        redis_key = AuthService._get_redis_key(email, token_type)
        
        await redis_client.set(redis_key, secret_token, ex=ttl_seconds)
        
        # Set cooldown
        await redis_client.set(
            cooldown_key, 
            "1", 
            ex=settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS
        )
        
        # Create composite token: base64(email).secret_token
        email_b64 = base64.urlsafe_b64encode(email.encode()).decode()
        composite_token = f"{email_b64}.{secret_token}"
        
        logger.info(f"Generated {token_type} token for email (masked)")
        
        return composite_token
    
    @staticmethod
    async def validate_token(
        redis_client: redis.Redis, 
        token: str, 
        token_type: str = "email_verification"
    ) -> Optional[str]:
        """
        Validate a verification token.
        Returns the email if valid, None otherwise.
        """
        try:
            if "." not in token:
                return None
                
            email_b64, secret_token = token.split(".", 1)
            email = base64.urlsafe_b64decode(email_b64.encode()).decode()
            
            redis_key = AuthService._get_redis_key(email, token_type)
            stored_token = await redis_client.get(redis_key)
            
            if not stored_token:
                logger.warning(f"No {token_type} token found for email")
                return None
            
            if secrets.compare_digest(stored_token, secret_token):
                return email
            return None
            
        except Exception:
            return None

    @staticmethod
    async def consume_token(
        redis_client: redis.Redis, 
        token: str, 
        token_type: str = "email_verification"
    ) -> Optional[str]:
        """
        Validate and consume (delete) a verification token.
        Returns the email if valid and consumed, None otherwise.
        """
        email = await AuthService.validate_token(redis_client, token, token_type)
        
        if not email:
            return None
        
        # Delete the token from Redis
        redis_key = AuthService._get_redis_key(email, token_type)
        await redis_client.delete(redis_key)
        
        logger.info(f"Consumed {token_type} token for email")
        
        return email
    
    @staticmethod
    async def invalidate_user_tokens(redis_client: redis.Redis, email: str) -> None:
        """
        Invalidate all tokens (verification and reset) for a user.
        """
        # Delete email verification token
        await redis_client.delete(AuthService._get_redis_key(email, AuthService.EMAIL_VERIFICATION_PREFIX))
        # Delete password reset token
        await redis_client.delete(AuthService._get_redis_key(email, AuthService.PASSWORD_RESET_PREFIX))
        
        logger.info(f"Invalidated all tokens for email {email}")

    @staticmethod
    async def reset_password(
        db: AsyncSession,
        redis_client: redis.Redis,
        token: str,
        new_password: str
    ) -> None:
        """
        Reset user password using token.
        """
        # Validate and consume token
        email = await AuthService.consume_token(
            redis_client, 
            token, 
            AuthService.PASSWORD_RESET_PREFIX
        )
        
        if not email:
            from app.core.exceptions import BadRequestException
            raise BadRequestException(detail="Invalid or expired password reset token")
            
        # Get user
        user = await UserService.get_user_by_email(db, email)
        if not user:
            from app.core.exceptions import NotFoundException
            raise NotFoundException(detail="User not found")
            
        if not user.is_active:
             from app.core.exceptions import AuthenticationException
             raise AuthenticationException(detail="User account is inactive")
        
        # Update password
        from app.core.security import hash_password
        user.password = hash_password(new_password)
        await db.commit()
        
        await AuthService.invalidate_user_tokens(redis_client, email)
        
        logger.info(f"Password reset successfully for user {email}")

