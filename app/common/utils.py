from sqlalchemy.sql import Select
from app.modules.users.model import User
from app.common.enums import UserRole

def apply_tenant_filter(query: Select, user: User, model) -> Select:
    """
    Apply tenant isolation filter to a query.
    
    If the user is a SUPER_ADMIN, returns the query as-is.
    Otherwise, adds a WHERE clause to filter by the user's tenant_id.
    """
    if user.role != UserRole.SUPER_ADMIN:
        return query.where(model.tenant_id == user.tenant_id)
    return query
