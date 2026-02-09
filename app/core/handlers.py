"""
Global exception handlers for standardized error responses.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    AuthenticationException,
    PermissionDeniedException,
    NotFoundException,
    TenantIsolationException,
    EmailNotVerifiedException,
    BadRequestException
)


async def bad_request_exception_handler(request: Request, exc: BadRequestException) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "status": "error",
            "message": "BAD_REQUEST",
            "error": {
                "details": exc.detail
            }
        }
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail,
            "error": {
                "details": exc.detail
            }
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        errors.append(f"{field}: {message}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "VALIDATION_ERROR",
            "error": {
                "details": "; ".join(errors) if errors else "Validation failed"
            }
        }
    )


async def authentication_exception_handler(request: Request, exc: AuthenticationException) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "status": "error",
            "message": "AUTHENTICATION_ERROR",
            "error": {
                "details": exc.detail
            }
        }
    )


async def permission_exception_handler(request: Request, exc: PermissionDeniedException) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "status": "error",
            "message": "PERMISSION_DENIED",
            "error": {
                "details": exc.detail
            }
        }
    )


async def not_found_exception_handler(request: Request, exc: NotFoundException) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "status": "error",
            "message": "NOT_FOUND",
            "error": {
                "details": exc.detail
            }
        }
    )


async def tenant_isolation_exception_handler(request: Request, exc: TenantIsolationException) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "status": "error",
            "message": "TENANT_ISOLATION_VIOLATION",
            "error": {
                "details": exc.detail
            }
        }
    )


async def email_not_verified_exception_handler(request: Request, exc: EmailNotVerifiedException) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "status": "error",
            "message": "EMAIL_NOT_VERIFIED",
            "error": {
                "details": exc.detail
            }
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "INTERNAL_ERROR",
            "error": {
                "details": str(exc) if hasattr(exc, '__str__') else None
            }
        }
    )

