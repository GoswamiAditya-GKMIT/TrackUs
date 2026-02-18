"""
User dependencies for fetching resources and validating permissions.
"""
import uuid
from typing import Literal

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.modules.users.model import User
from app.common.enums import UserRole
from app.dependencies.auth import get_current_user
from app.core.exceptions import (
    NotFoundException, 
    PermissionDeniedException, 
    TenantIsolationException
)
from app.common.utils import apply_tenant_filter


async def get_user_or_404(
    user_id: uuid.UUID = Path(..., description="The ID of the user to fetch"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> User:

    query = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    
    query = apply_tenant_filter(query, current_user, User)
    
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise NotFoundException(detail="User not found")
        
    return user


class TargetUserValidator:
    """
    Dependency validator to ensure the current user has permission 
    to access/modify the target user.
    """
    def __init__(self, action: Literal["access", "update", "delete"] = "access"):
        self.action = action

    async def __call__(
        self,
        user: User = Depends(get_user_or_404),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        
        # Super Admin logic
        if current_user.role == UserRole.SUPER_ADMIN:
            if user.role != UserRole.TENANT_ADMIN:
                 raise PermissionDeniedException(
                    detail=f"Super admins can only {self.action} tenant admins"
                )
            
            if self.action == "delete":
                # Check if this is the last tenant admin
                query = select(func.count(User.id)).where(
                    User.tenant_id == user.tenant_id,
                    User.role == UserRole.TENANT_ADMIN,
                    User.deleted_at.is_(None)
                )
                result = await db.execute(query)
                count = result.scalar()
                if count <= 1:
                    raise PermissionDeniedException(
                        detail="Cannot delete the last tenant admin of an organization"
                    )
            return user

        # Tenant Admin logic
        if current_user.role == UserRole.TENANT_ADMIN:
            if user.tenant_id != current_user.tenant_id:
                raise TenantIsolationException(
                    detail=f"Cannot {self.action} users from other tenants"
                )
            
            # Block self-deletion
            if self.action == "delete" and user.id == current_user.id:
                raise PermissionDeniedException(
                    detail="Tenant admins cannot delete themselves"
                )

            # Allow self-update/access, but restrict other modifications to regular users
            if user.id != current_user.id and user.role != UserRole.USER:
                raise PermissionDeniedException(
                    detail=f"Tenant admins can only {self.action} regular users"
                )
            return user

        # Regular User logic
        # Users can only access/update/delete themselves
        if user.id != current_user.id:
            msg = "Users cannot access other user details"
            if self.action == "update":
                msg = "Users can only update their own profile"
            elif self.action == "delete":
                msg = "Users can only delete their own account"
                
            raise PermissionDeniedException(detail=msg)
            
        return user
