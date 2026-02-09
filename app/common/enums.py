"""
Shared enums used across the application.
"""
from enum import Enum


class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    TENANT_ADMIN = "TENANT_ADMIN"
    USER = "USER"


class GroupMemberRole(str, Enum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class MessageType(str, Enum):
    TEXT = "TEXT"
    SYSTEM = "SYSTEM"


class EventStatus(str, Enum):
    PLANNED = "PLANNED"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ParticipantStatus(str, Enum):
    INVITED = "INVITED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    LEFT = "LEFT"
    REMOVED = "REMOVED"


class NotificationType(str, Enum):
    USER_JOINED_GROUP = "USER_JOINED_GROUP"
    USER_LEFT_GROUP = "USER_LEFT_GROUP"
    EVENT_CREATED = "EVENT_CREATED"
    EVENT_STARTED = "EVENT_STARTED"
    EVENT_ENDED = "EVENT_ENDED"
    EVENT_INVITATION = "EVENT_INVITATION"
    NEW_MESSAGE = "NEW_MESSAGE"


class ReferenceType(str, Enum):
    GROUP = "GROUP"
    TRAVEL_EVENT = "TRAVEL_EVENT"
    MESSAGE = "MESSAGE"
    USER = "USER"
