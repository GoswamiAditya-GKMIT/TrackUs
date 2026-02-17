"""
Notification schemas.
"""
from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class NotificationBase(BaseModel):
    type: str
    title: str
    message: str
    reference_type: str
    reference_id: Optional[UUID] = None
    is_read: bool = False

class NotificationCreate(NotificationBase):
    pass

class NotificationUpdate(BaseModel):
    is_read: bool

class NotificationResponse(NotificationBase):
    id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class UnreadCountResponse(BaseModel):
    count: int
