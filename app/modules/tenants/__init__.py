"""Tenants module initialization."""
from app.modules.tenants.model import Tenant
from app.modules.tenants.router import router

__all__ = ["Tenant", "router"]
