"""
User service layer - business logic for user operations.
"""
import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.modules.users.model import User
from app.modules.users.schema import UserCreate, UserUpdate
from app.modules.users.tasks import send_verification_email
from app.modules.tenants.service import TenantService
from app.core.security import hash_password
from app.core.redis import get_redis
from app.core.exceptions import (
    NotFoundException,
    PermissionDeniedException,
    BadRequestException
)
from app.common.enums import UserRole


class UserService:
    
    @staticmethod
    async def create_user(
        db: AsyncSession,
        user_data: UserCreate,
        creator: User
    ) -> tuple[User, str]:
        """
        Create a new user.
        Validation of who can create whom is done in Router/Dependencies.
        """
        if creator.role == UserRole.SUPER_ADMIN:
            # SUPER_ADMIN must provide tenant_id
            if not user_data.tenant_id:
                raise BadRequestException(
                    detail="tenant_id is required when creating tenant admin"
                )
            
            # Verify tenant exists
            await TenantService.get_tenant(db, user_data.tenant_id)
            
            # Role implicitly set to TENANT_ADMIN
            role = UserRole.TENANT_ADMIN
            tenant_id = user_data.tenant_id
            
        elif creator.role == UserRole.TENANT_ADMIN:
            # TENANT_ADMIN must NOT provide tenant_id
            if user_data.tenant_id:
                raise BadRequestException(
                    detail="tenant_id should not be provided by tenant admin"
                )
            
            # tenant_id and role implicitly set
            tenant_id = creator.tenant_id
            role = UserRole.USER
            
        else:
            raise PermissionDeniedException(
                detail="Only admins can create users"
            )
        
        query = select(User).where(
            User.email == user_data.email
        )
        result = await db.execute(query)
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise BadRequestException(
                detail=f"User with email '{user_data.email}' already exists"
            )
        
        user = User(
            tenant_id=tenant_id,
            email=user_data.email,
            hashed_password=hash_password(user_data.password),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            role=role,
            is_active=False,
            is_email_verified=False  # Will be set to True on verification
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        from app.modules.auth.service import AuthService
        
        redis_client = await get_redis()
        token = await AuthService.generate_and_store_token(redis_client, user.email)
        
        return user, token
    
    @staticmethod
    async def verify_user_email(
        db: AsyncSession,
        redis_client,
        token: str
    ) -> User:

        from app.modules.auth.service import AuthService
        
        # Validate and consume token (returns email if valid)
        email = await AuthService.consume_token(redis_client, token)
        
        if not email:
            raise BadRequestException(
                detail="Invalid or expired verification token"
            )
        
        query = select(User).where(
            User.email == email,
            User.deleted_at.is_(None)
        )
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundException(detail="User not found")
        
        if user.is_email_verified:
            raise BadRequestException(
                detail="Email already verified"
            )
        
        # Activate user and mark email as verified
        user.is_email_verified = True
        user.is_active = True
        
        await db.commit()
        await db.refresh(user)
        
        return user
    
    @staticmethod
    async def get_user(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> User:

        query = select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None)
        ).options(selectinload(User.tenant))
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundException(detail="User not found")
        
        return user
    
    @staticmethod
    async def get_user_by_email(
        db: AsyncSession,
        email: str
    ) -> Optional[User]:

        query = select(User).where(
            User.email == email,
            User.deleted_at.is_(None)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def list_users(
        db: AsyncSession,
        current_user: User, 
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        deleted: Optional[bool] = None
    ) -> tuple[list[User], int]:

        query = select(User).options(selectinload(User.tenant))
        
        # Handle soft-delete filtering
        if deleted is True:
            # Fetch ONLY deleted
            query = query.where(User.deleted_at.isnot(None))
        elif deleted is False:
            # Fetch ONLY non-deleted (active)
            query = query.where(User.deleted_at.is_(None))
        # If deleted is None, fetch ALL (both deleted and non-deleted)
        
        if current_user.role == UserRole.SUPER_ADMIN:
            query = query.where(User.role == UserRole.TENANT_ADMIN)
            
        elif current_user.role in [UserRole.TENANT_ADMIN, UserRole.USER]:
            query = query.where(
                User.tenant_id == current_user.tenant_id,
                User.role == UserRole.USER
            )
        
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
        result = await db.execute(query)
        users = list(result.scalars().all())
        
        return users, total
    
    @staticmethod
    async def update_user(
        db: AsyncSession,
        user: User, 
        user_data: UserUpdate,
        current_user: User
    ) -> User:

        if user_data.first_name is not None:
            user.first_name = user_data.first_name
        if user_data.last_name is not None:
            user.last_name = user_data.last_name
            
        if user_data.is_active is not None:

            if current_user.role in [UserRole.SUPER_ADMIN, UserRole.TENANT_ADMIN]:
                user.is_active = user_data.is_active
                if user_data.is_active:
                    user.restore()
            else:
                 raise PermissionDeniedException(
                    detail="Users cannot update is_active field"
                )
        
        await db.commit()
        await db.refresh(user)
        
        return user
    
    @staticmethod
    async def resend_verification_email(
        db: AsyncSession,
        email: str
    ) -> tuple[User, str]:
        """
        Resend verification email to user.
        Automatically invalidates any old tokens when generating new one.
        """
        user = await UserService.get_user_by_email(db, email)
        
        if not user:
            raise NotFoundException(detail="User not found")
        
        if user.is_email_verified:
            raise BadRequestException(detail="Email already verified")
        
        from app.modules.auth.service import AuthService
        
        redis_client = await get_redis()
        token = await AuthService.generate_and_store_token(redis_client, email)

        
        return user, token
    
    @staticmethod
    async def delete_user(
        db: AsyncSession,
        redis_client,
        user: User, 
        current_user: User 
    ) -> None:
        from app.modules.auth.service import AuthService

        # Invalidate any pending verification tokens
        try:
            await AuthService.invalidate_user_tokens(redis_client, user.email)
        except Exception:
            pass

        user.is_active = False
        user.soft_delete()
        await db.commit()
        
        if user.id == current_user.id:
            pass
