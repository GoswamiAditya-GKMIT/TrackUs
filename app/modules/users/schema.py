"""
User Pydantic schemas.
"""
from typing import Optional
import uuid
from datetime import datetime

from pydantic import EmailStr, Field, field_validator, model_validator

from app.common.schemas import BaseSchema, BaseResponseSchema
from app.common.enums import UserRole
from app.common.utils import validate_password, PasswordStr


from app.modules.tenants.schema import TenantResponse


class UserCreate(BaseSchema):
    
    email: EmailStr
    password: PasswordStr
    confirm_password: PasswordStr
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    tenant_id: Optional[uuid.UUID] = None  # Required for SUPER_ADMIN creating TENANT_ADMIN
    
    
    @model_validator(mode='after')
    def validate_passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class UserUpdate(BaseSchema):
    
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    is_active: Optional[bool] = None


class UserBaseResponse(BaseResponseSchema):
    """Base user response schema with common fields."""
    email: str
    first_name: str
    last_name: str
    role: UserRole
    is_active: bool
    is_email_verified: bool
    deleted_at: Optional[datetime] = None
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class UserResponse(UserBaseResponse):
    """Standard user response with tenant ID."""
    tenant_id: Optional[uuid.UUID]


class UserListResponse(UserResponse):
    """User response for list view, includes tenant name."""
    tenant_name: Optional[str] = None


class UserDetailResponse(UserBaseResponse):
    """User response for detail view, includes nested tenant data but excludes tenant_id."""
    tenant: Optional[TenantResponse] = None