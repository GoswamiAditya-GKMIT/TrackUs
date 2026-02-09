"""
Helper functions for creating standardized API responses.
"""
from typing import Any


from app.common.responses import SuccessResponse, PaginatedResponse


def success_response(
    message: str,
    data: Any
) -> dict:
    return SuccessResponse(
        message=message,
        data=data
    ).model_dump()


def paginated_response(
    message: str,
    data: list,
    total: int,
    skip: int,
    limit: int
) -> dict:
    return PaginatedResponse(
        message=message,
        data=data,
        total=total,
        skip=skip,
        limit=limit
    ).model_dump()
