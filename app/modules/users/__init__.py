"""Users module initialization."""
from app.modules.users.model import User
from app.modules.users.router import router

__all__ = ["User", "router"]
