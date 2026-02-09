"""
Tenant dependencies for fetching resources and validating permissions.
"""
import uuid

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.modules.tenants.model import Tenant
from app.dependencies.auth import get_current_user, require_super_admin
from app.common.enums import UserRole
from app.modules.users.model import User
from app.core.exceptions import NotFoundException, PermissionDeniedException


async def get_tenant_or_404(
    tenant_id: uuid.UUID = Path(..., description="The ID of the tenant to fetch"),
    db: AsyncSession = Depends(get_db)
) -> Tenant:
    query = select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
    result = await db.execute(query)
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise NotFoundException(detail="Tenant not found")
        
    return tenant



async def get_tenant_or_404_including_deleted(
    tenant_id: uuid.UUID = Path(..., description="The ID of the tenant to fetch"),
    db: AsyncSession = Depends(get_db)
) -> Tenant:
    """
    Fetch a tenant by ID (including deleted) or raise 404.
    """
    query = select(Tenant).where(Tenant.id == tenant_id)
    result = await db.execute(query)
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise NotFoundException(detail="Tenant not found")
        
    return tenant

async def get_valid_tenant(
    tenant: Tenant = Depends(get_tenant_or_404_including_deleted),
    current_user: User = Depends(require_super_admin)
) -> Tenant:

    return tenant

async def get_valid_tenant_for_delete(
    tenant: Tenant = Depends(get_tenant_or_404),
    current_user: User = Depends(require_super_admin)
) -> Tenant:

    return tenant