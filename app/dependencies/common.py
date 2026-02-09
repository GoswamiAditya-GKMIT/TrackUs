"""
Common dependencies used across multiple modules.
"""
from fastapi import Query
from pydantic import BaseModel, ConfigDict


class PaginationParams(BaseModel):
    """
    Common pagination parameters dependency.
    """
    skip: int = Query(0, ge=0, description="Number of items to skip")
    limit: int = Query(100, ge=1, le=100, description="Number of items to return")
    
    model_config = ConfigDict(frozen=True)
