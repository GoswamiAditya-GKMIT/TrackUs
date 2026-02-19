"""
Tenant Pydantic schemas.
"""
from typing import Optional
from datetime import datetime

from pydantic import Field, field_validator
from app.common.schemas import BaseSchema, BaseResponseSchema
from app.common.utils import NonEmptyStr, OptionalNonEmptyStr


class TenantCreate(BaseSchema):
    
    name: NonEmptyStr
    description: Optional[str] = Field(None, max_length=1000)


class TenantUpdate(BaseSchema):
    
    name: OptionalNonEmptyStr = None
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None


class TenantResponse(BaseResponseSchema):
    
    name: str
    description: Optional[str]
    is_active: bool
    user_count: int = 0
    deleted_at: Optional[datetime] = None


class TenantDetailResponse(TenantResponse):
    active_group_count: int = 0
    active_event_count: int = 0
