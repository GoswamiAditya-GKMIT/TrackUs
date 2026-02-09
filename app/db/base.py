"""
SQLAlchemy declarative base and model imports.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass

def import_models():
    """Import all models to register them with SQLAlchemy."""

