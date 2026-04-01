from datetime import datetime
from typing import Optional
import uuid

from pydantic import Field
from app.common.schemas import BaseSchema
from app.common.enums import GroupMemberRole
from app.modules.users.schema import UserResponse


class GroupBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class GroupResponse(GroupBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_by: Optional[uuid.UUID]
    is_active: bool
    member_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GroupAdminResponse(GroupResponse):
    deleted_at: Optional[datetime]


class GroupMemberBase(BaseSchema):
    user_id: uuid.UUID
    role: GroupMemberRole = GroupMemberRole.MEMBER


class GroupMemberCreate(GroupMemberBase):
    pass


class GroupMemberUpdate(BaseSchema):
    role: GroupMemberRole


class GroupMemberResponse(GroupMemberBase):
    group_id: uuid.UUID
    joined_at: datetime = Field(alias="created_at")
    left_at: Optional[datetime] = None
    user_name: str
    user_email: str

    class Config:
        from_attributes = True
        populate_by_name = True


class GroupDetailResponse(GroupResponse):
    pass


class GroupDetailAdminResponse(GroupAdminResponse):
    pass
