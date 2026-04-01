"""
Authentication Pydantic schemas.
"""
from typing import Optional
from pydantic import EmailStr, Field, field_validator, model_validator

from app.common.schemas import BaseSchema
from app.modules.users.schema import UserResponse
from app.common.utils import validate_password, PasswordStr


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


class ResendVerificationRequest(BaseSchema):
    
    email: EmailStr = Field(..., description="User's email address")


class ForgotPasswordRequest(BaseSchema):
    
    email: EmailStr = Field(..., description="User's email address")


class ResetPasswordRequest(BaseSchema):
    
    token: str = Field(..., min_length=1, description="Password reset token")
    new_password: PasswordStr
    confirm_password: PasswordStr

    
    @model_validator(mode='after')
    def validate_passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class CurrentUser(UserResponse):
    pass


class LogoutRequest(BaseSchema):
    refresh_token: Optional[str] = Field(None, description="Optional refresh token to blacklist")
