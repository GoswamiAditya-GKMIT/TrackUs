"""
Authentication Pydantic schemas.
"""
from pydantic import EmailStr, Field

from app.common.schemas import BaseSchema
from app.modules.users.schema import UserResponse


class LoginRequest(BaseSchema):
    
    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseSchema):
    
    access_token: str
    refresh_token: str


class RefreshTokenRequest(BaseSchema):
    
    refresh_token: str


class EmailVerificationRequest(BaseSchema):
    
    token: str = Field(..., min_length=1, description="Email verification token")


class CurrentUser(UserResponse):
    pass
