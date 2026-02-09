"""
Standardized API response schemas.
"""
from typing import Generic, TypeVar, Optional, Any, List
from pydantic import BaseModel, Field

DataT = TypeVar('DataT')


class SuccessResponse(BaseModel, Generic[DataT]):
    """Standard success response wrapper."""
    
    status: str = Field(default="success", description="Response status")
    message: str = Field(..., description="Success message")
    data: Optional[DataT] = Field(None, description="Response data")


class PaginatedResponse(SuccessResponse[List[DataT]]):
    """Standard paginated success response."""
    
    total: int = Field(..., description="Total number of items")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum number of items")


class ErrorDetail(BaseModel):
    """Error detail information."""
    
    details: Optional[Any] = Field(None, description="Error details")


class ErrorResponse(BaseModel):
    """Standard error response wrapper."""
    
    status: str = Field(default="error", description="Response status")
    message: str = Field(..., description="Error code/type")
    error: ErrorDetail = Field(..., description="Error details")
