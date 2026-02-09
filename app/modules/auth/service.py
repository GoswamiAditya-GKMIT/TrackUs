"""
Authentication service layer - business logic for authentication.
"""

from sqlalchemy.ext.asyncio import AsyncSession

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
import uuid



class AuthService:
    """Service class for authentication operations."""
    
    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        email: str,
        password: str
    ) -> User:

        user = await UserService.get_user_by_email(db, email)
        
        if not user:
            raise AuthenticationException(detail="Invalid email or password")
        
        if not verify_password(password, user.hashed_password):
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
        if not user_id:
            raise AuthenticationException(detail="Invalid token payload")
        
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

