"""
Authentication Pydantic schemas.
"""
from pydantic import EmailStr, Field, field_validator, model_validator

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


class ResendVerificationRequest(BaseSchema):
    
    email: EmailStr = Field(..., description="User's email address")


class ForgotPasswordRequest(BaseSchema):
    
    email: EmailStr = Field(..., description="User's email address")


class ResetPasswordRequest(BaseSchema):
    
    token: str = Field(..., min_length=1, description="Password reset token")
    new_password: str = Field(..., min_length=8, max_length=100)
    confirm_password: str = Field(..., min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v
    
    @model_validator(mode='after')
    def validate_passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class CurrentUser(UserResponse):
    pass
