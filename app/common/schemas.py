"""
Base Pydantic schemas for common patterns.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class BaseResponseSchema(BaseSchema):
    
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PaginationParams(BaseModel):
    
    skip: int = 0
    limit: int = 100
    
    model_config = ConfigDict(frozen=True)


class PaginatedResponse(BaseModel):
    
    total: int
    skip: int
    limit: int
    items: list
