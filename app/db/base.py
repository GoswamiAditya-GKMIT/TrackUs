"""
SQLAlchemy declarative base and model imports.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def import_models():
    """Import all models to register them with SQLAlchemy."""
    from app.modules.users.model import User
    from app.modules.tenants.model import Tenant
    from app.modules.auth.model import TokenBlacklist
    from app.modules.groups.model import Group, GroupMember
    from app.modules.chat.model import GroupMessage


