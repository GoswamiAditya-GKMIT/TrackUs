"""
Tenant Pydantic schemas.
"""
from typing import Optional
from datetime import datetime

from pydantic import Field, field_validator

from app.common.schemas import BaseSchema, BaseResponseSchema


class TenantCreate(BaseSchema):
    
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Tenant name cannot be empty")
        return v.strip()


class TenantUpdate(BaseSchema):
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Tenant name cannot be empty")
        return v.strip() if v else None


class TenantResponse(BaseResponseSchema):
    
    name: str
    description: Optional[str]
    is_active: bool
    deleted_at: Optional[datetime] = None
