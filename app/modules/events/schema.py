"""
Travel Event schemas for request/response validation.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.common.enums import EventStatus


class EventCreate(BaseModel):
    name: str = Field(..., max_length=100, description="Event name")
    destination: str = Field(..., max_length=100, description="Event destination")
    start_time: datetime = Field(..., description="Event start time")
    end_time: datetime = Field(..., description="Event end time")
    
    @model_validator(mode='after')
    def validate_time_range(self) -> 'EventCreate':
        """Validate that end_time is after start_time."""
        if self.end_time <= self.start_time:
            raise ValueError('End time must be after start time')
        return self


class EventResponse(BaseModel):
    id: uuid.UUID
    name: str
    destination: str
    start_time: datetime
    end_time: datetime
    status: str
    created_by: uuid.UUID
    creator_name: Optional[str] = None
    participant_count: Optional[int] = None
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


class ParticipantResponse(BaseModel):
    """Participant response schema."""
    id: uuid.UUID
    user_id: uuid.UUID
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    status: str
    responded_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ParticipantAddRequest(BaseModel):
    """Request to add a participant to an event."""
    user_id: uuid.UUID = Field(..., description="ID of the user to add as participant")
