from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, Field, ConfigDict


class LocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")


class LocationResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    user_id: uuid.UUID
    latitude: float
    longitude: float
    is_active: bool
    last_updated_at: datetime
    
    # Optional user details for better UI
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
