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
    TenantResponse,
    TenantDetailResponse
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
        data=tenant
    )


@router.get(
    "/{tenant_id}",
    response_model=SuccessResponse[TenantDetailResponse],
    summary="Get tenant by ID"
)
async def get_tenant(
    tenant: Tenant = Depends(get_valid_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a tenant by ID (SUPER_ADMIN only).
    Permissions handled by `get_valid_tenant` dependency.
    """
    await TenantService.populate_tenant_stats(db, tenant)
    
    return success_response(
        message="Tenant retrieved successfully",
        data=tenant
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
        data=tenants,
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
        data=updated_tenant
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
