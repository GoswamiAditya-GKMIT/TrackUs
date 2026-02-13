"""
Travel Event schemas for request/response validation.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.common.enums import EventStatus


class EventCreate(BaseModel):
    name: str = Field(..., max_length=100, description="Event name")
    destination: str = Field(..., max_length=100, description="Event destination")
    start_time: datetime = Field(..., description="Event start time")
    end_time: datetime = Field(..., description="Event end time")
    
    @field_validator('end_time')
    @classmethod
    def validate_time_range(cls, end_time: datetime, info) -> datetime:
        """Validate that end_time is after start_time."""
        start_time = info.data.get('start_time')
        if start_time and end_time <= start_time:
            raise ValueError('End time must be after start time')
        return end_time


class EventResponse(BaseModel):
    id: uuid.UUID
    name: str
    destination: str
    start_time: datetime
    end_time: datetime
    status: str
    created_by: uuid.UUID
    creator_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class EventUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    destination: Optional[str] = Field(None, max_length=100)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[EventStatus] = None
