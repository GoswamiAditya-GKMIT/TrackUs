"""Dependencies module initialization."""
from app.dependencies.auth import (
    get_current_user,
    require_super_admin,
    require_tenant_admin,
    require_admin
)
__all__ = [
    "get_current_user",
    "require_super_admin",
    "require_tenant_admin",
]
