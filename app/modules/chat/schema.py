"""
Chat Pydantic schemas.
"""
from datetime import datetime
from typing import Optional
import uuid

from pydantic import Field
from app.common.schemas import BaseSchema
from app.common.enums import MessageType
from app.modules.users.schema import UserResponse


class ChatMessageBase(BaseSchema):
    message: str = Field(..., min_length=1)


class ChatMessageCreate(ChatMessageBase):
    message_type: MessageType = MessageType.TEXT


class ChatMessageResponse(ChatMessageBase):
    message_id: uuid.UUID = Field(alias="id")
    message_type: MessageType
    sender_id: Optional[uuid.UUID]
    sender_name: Optional[str]

    class Config:
        from_attributes = True
        populate_by_name = True
