"""
Tenant router - HTTP endpoints for tenant operations.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.tenants.schema import (
    TenantCreate,
    TenantUpdate,
    TenantResponse
)
from app.modules.tenants.model import Tenant
from app.modules.tenants.service import TenantService
from app.modules.users.model import User
from app.dependencies.auth import require_super_admin
from app.dependencies.tenants import (
    get_valid_tenant, 
    get_valid_tenant_for_delete
)
from app.common.response_utils import success_response, paginated_response
from app.common.responses import SuccessResponse, PaginatedResponse
from fastapi import Response
from app.dependencies.common import PaginationParams

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post(
    "/",
    response_model=SuccessResponse[TenantResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tenant"
)
async def create_tenant(
    tenant_data: TenantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):

    tenant = await TenantService.create_tenant(db, tenant_data)
    
    return success_response(
        message="Tenant created successfully",
        data={
            "id": str(tenant.id),
            "name": tenant.name,
            "description": tenant.description,
            "is_active": tenant.is_active,
            "created_at": tenant.created_at.isoformat(),
            "updated_at": tenant.updated_at.isoformat(),
            "deleted_at": tenant.deleted_at.isoformat() if tenant.deleted_at else None
        }
    )


@router.get(
    "/{tenant_id}",
    response_model=SuccessResponse[TenantResponse],
    summary="Get tenant by ID"
)
async def get_tenant(
    tenant: Tenant = Depends(get_valid_tenant)
):
    """
    Get a tenant by ID (SUPER_ADMIN only).
    Permissions handled by `get_valid_tenant` dependency.
    """
    return success_response(
        message="Tenant retrieved successfully",
        data={
            "id": str(tenant.id),
            "name": tenant.name,
            "description": tenant.description,
            "is_active": tenant.is_active,
            "created_at": tenant.created_at.isoformat(),
            "updated_at": tenant.updated_at.isoformat(),
            "deleted_at": tenant.deleted_at.isoformat() if tenant.deleted_at else None
        }
    )


@router.get(
    "/",
    response_model=PaginatedResponse[TenantResponse],
    summary="List all tenants"
)
async def list_tenants(
    pagination: PaginationParams = Depends(),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    deleted: Optional[bool] = Query(None, description="Filter by deleted status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    tenants, total = await TenantService.list_tenants(db, pagination.skip, pagination.limit, is_active, deleted)
    
    return paginated_response(
        message="Tenants retrieved successfully",
        data=[
            {
                "id": str(t.id),
                "name": t.name,
                "description": t.description,
                "is_active": t.is_active,
                "created_at": t.created_at.isoformat() if hasattr(t, 'created_at') else None,
                "updated_at": t.updated_at.isoformat() if hasattr(t, 'updated_at') else None,
                "deleted_at": t.deleted_at.isoformat() if t.deleted_at else None
            }
            for t in tenants
        ],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )


@router.patch(
    "/{tenant_id}",
    response_model=SuccessResponse[TenantResponse],
    summary="Update a tenant"
)
async def update_tenant(
    tenant_data: TenantUpdate,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_valid_tenant)
):
    """
    Update a tenant (SUPER_ADMIN only).
    """
    updated_tenant = await TenantService.update_tenant(db, tenant, tenant_data)
    
    return success_response(
        message="Tenant updated successfully",
        data={
            "id": str(updated_tenant.id),
            "name": updated_tenant.name,
            "description": updated_tenant.description,
            "is_active": updated_tenant.is_active,
            "created_at": updated_tenant.created_at.isoformat(),
            "updated_at": updated_tenant.updated_at.isoformat(),
            "deleted_at": updated_tenant.deleted_at.isoformat() if updated_tenant.deleted_at else None
        }
    )


@router.delete(
    "/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a tenant"
)
async def delete_tenant(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_valid_tenant_for_delete)
):
    await TenantService.delete_tenant(db, tenant)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
