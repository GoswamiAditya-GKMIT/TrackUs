from typing import Annotated, Optional
from pydantic import AfterValidator, Field, StringConstraints
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


def validate_password(v: str) -> str:
    """
    Common password validator.
    - Min 8 characters
    - At least one lowercase letter
    - At least one digit
    """
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not any(c.islower() for c in v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in v):
        raise ValueError("Password must contain at least one digit")
    return v


PasswordStr = Annotated[
    str, 
    Field(min_length=8, max_length=100), 
    AfterValidator(validate_password)
]


NonEmptyStr = Annotated[
    str, 
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]

OptionalNonEmptyStr = Annotated[
    Optional[str], 
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
