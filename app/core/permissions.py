"""
Core permission helpers and access control logic.
"""
import uuid

from app.modules.users.model import User
from app.common.enums import UserRole
from app.core.exceptions import PermissionDeniedException, TenantIsolationException


def require_super_admin(current_user: User) -> None:

    if current_user.role != UserRole.SUPER_ADMIN:
        raise PermissionDeniedException(
            detail="Only super admins can perform this action"
        )


def require_tenant_admin(current_user: User) -> None:
    """
    Verify that the current user is a TENANT_ADMIN.
    """
    if current_user.role != UserRole.TENANT_ADMIN:
        raise PermissionDeniedException(
            detail="Only tenant admins can perform this action"
        )


def validate_tenant_isolation(current_user: User, target_tenant_id: uuid.UUID) -> None:
    """
        current_user: Currently authenticated user
        target_tenant_id: Tenant ID being accessed
        
    Raises:
        TenantIsolationException: If non-super-admin trying to access other tenant
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        return  # Super admin can access all tenants
    
    if current_user.tenant_id != target_tenant_id:
        raise TenantIsolationException(
            detail="Cannot access resources from other tenants"
        )
