"""
Tenant service layer - business logic for tenant operations.
"""
import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenants.model import Tenant
from app.modules.users.model import User
from app.modules.groups.model import Group
from app.modules.events.model import TravelEvent
from app.modules.events.model import EventStatus
from app.modules.tenants.schema import TenantCreate, TenantUpdate
from app.core.exceptions import NotFoundException, BadRequestException
from sqlalchemy import select, func, and_


class TenantService:
    
    @staticmethod
    async def populate_tenant_stats(db: AsyncSession, tenant: Tenant) -> Tenant:
        """Populate statistic counts for the tenant."""
        
        user_count_query = select(func.count()).select_from(User).where(
            and_(
                User.tenant_id == tenant.id,
                User.deleted_at.is_(None)
            )
        )
        tenant.user_count = (await db.execute(user_count_query)).scalar()

        group_count_query = select(func.count()).select_from(Group).where(
            and_(
                Group.tenant_id == tenant.id,
                Group.deleted_at.is_(None)
            )
        )
        tenant.active_group_count = (await db.execute(group_count_query)).scalar()

        event_count_query = select(func.count()).select_from(TravelEvent).where(
            and_(
                TravelEvent.tenant_id == tenant.id,
                TravelEvent.deleted_at.is_(None),
                TravelEvent.status != EventStatus.CANCELLED
            )
        )
        tenant.active_event_count = (await db.execute(event_count_query)).scalar()
        
        return tenant

    
    @staticmethod
    async def create_tenant(
        db: AsyncSession,
        tenant_data: TenantCreate
    ) -> Tenant:

        # Check if tenant with same name exists
        query = select(Tenant).where(
            Tenant.name == tenant_data.name
        )
        result = await db.execute(query)
        existing_tenant = result.scalar_one_or_none()
        
        if existing_tenant:
            raise BadRequestException(detail="Tenant already exists")
        
        # Create new tenant
        tenant = Tenant(
            name=tenant_data.name,
            description=tenant_data.description
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        
        return tenant
    
    @staticmethod
    async def get_tenant(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        include_deleted: bool = False
    ) -> Tenant:

        query = select(Tenant).where(Tenant.id == tenant_id)
        
        if not include_deleted:
            query = query.where(Tenant.deleted_at.is_(None))
            
        result = await db.execute(query)
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise NotFoundException(detail="Tenant not found")

        # Counts
        await TenantService.populate_tenant_stats(db, tenant)
        
        return tenant
    
    @staticmethod
    async def list_tenants(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        deleted: Optional[bool] = None
    ) -> tuple[list[Tenant], int]:

        query = select(Tenant)
        
        if deleted is True:
            query = query.where(Tenant.deleted_at.isnot(None))
        elif deleted is False:
            query = query.where(Tenant.deleted_at.is_(None))        
        if is_active is not None:
            query = query.where(Tenant.is_active == is_active)
        
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        query = query.offset(skip).limit(limit).order_by(Tenant.created_at.desc())
        result = await db.execute(query)
        tenants = list(result.scalars().all())
        
        # Populate user_count for each tenant
        for tenant in tenants:
            
            user_count_query = select(func.count()).select_from(User).where(
                and_(
                    User.tenant_id == tenant.id,
                    User.deleted_at.is_(None)
                )
            )
            tenant.user_count = (await db.execute(user_count_query)).scalar()
        
        return tenants, total
        
        return tenants, total
    
    @staticmethod
    async def update_tenant(
        db: AsyncSession,
        tenant: Tenant,
        tenant_data: TenantUpdate
    ) -> Tenant:

        if tenant_data.name and tenant_data.name != tenant.name:
            query = select(Tenant).where(
                Tenant.name == tenant_data.name,
                Tenant.id != tenant.id,
                Tenant.deleted_at.is_(None)
            )
            result = await db.execute(query)
            existing_tenant = result.scalar_one_or_none()
            
            if existing_tenant:
                raise BadRequestException(detail="Tenant already exists")
        
        if tenant_data.name is not None:
            tenant.name = tenant_data.name
        if tenant_data.description is not None:
            tenant.description = tenant_data.description
        if tenant_data.is_active is not None:
            tenant.is_active = tenant_data.is_active
            if tenant_data.is_active:
                tenant.restore()
        
        await db.commit()
        await db.refresh(tenant)
        
        return tenant
    
    @staticmethod
    async def delete_tenant(
        db: AsyncSession,
        tenant: Tenant
    ) -> None:

        tenant.is_active = False
        tenant.soft_delete()
        await db.commit()
