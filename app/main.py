"""
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.db.base import import_models
from app.db.session import async_engine
from app.core.redis import init_redis, close_redis

from app.core.handlers import (
    http_exception_handler,
    validation_exception_handler,
    authentication_exception_handler,
    permission_exception_handler,
    not_found_exception_handler,
    tenant_isolation_exception_handler,
    email_not_verified_exception_handler,
    bad_request_exception_handler,
    general_exception_handler
)
from app.core.exceptions import (
    AuthenticationException,
    PermissionDeniedException,
    NotFoundException,
    TenantIsolationException,
    EmailNotVerifiedException,
    BadRequestException
)

from app.modules.auth.router import router as auth_router
from app.modules.tenants.router import router as tenants_router
from app.modules.users.router import router as users_router
from app.modules.groups.router import router as groups_router
from app.modules.chat.router import router as chat_router
from app.realtime.pubsub import pubsub_manager
from app.realtime.manager import manager
from app.realtime.chat import chat_socket_handler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def handle_pubsub_message(channel: str, message: dict):
    """
    Handle incoming Pub/Sub messages and broadcast to local WebSocket connections.
    
    Args:
        channel: Redis channel (e.g., "group:123")
        message: Message dict to broadcast
    """
    # Extract group_id from channel name (format: "group:{group_id}")
    group_id = channel.split(":", 1)[1] if ":" in channel else channel
    await manager._broadcast_local(group_id, message)


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Starting TrackUs application...")
    
    import_models()
    await init_redis()
    
    # Initialize Redis Pub/Sub for WebSocket scaling
    try:
        await pubsub_manager.connect()
        # Register handler for group messages
        pubsub_manager.register_handler("group:*", handle_pubsub_message)
        await pubsub_manager.start_subscriber()
        logger.info("Redis Pub/Sub initialized successfully")
        # Update manager to use Pub/Sub
        manager.pubsub = pubsub_manager
    except Exception as e:
        logger.warning(f"Failed to initialize Redis Pub/Sub: {e}. Running in local-only mode.")

    logger.info("Application startup complete")

    yield
    
    logger.info("Shutting down TrackUs application...")
    await pubsub_manager.disconnect()
    await close_redis()
    await async_engine.dispose()
    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Multi-tenant travel coordination platform backend",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={
        "persistAuthorization": True
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(BadRequestException, bad_request_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(AuthenticationException, authentication_exception_handler)
app.add_exception_handler(PermissionDeniedException, permission_exception_handler)
app.add_exception_handler(NotFoundException, not_found_exception_handler)
app.add_exception_handler(TenantIsolationException, tenant_isolation_exception_handler)
app.add_exception_handler(EmailNotVerifiedException, email_not_verified_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(tenants_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(groups_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")

app.add_api_websocket_route("/chat/groups/{group_id}", chat_socket_handler)


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.get("/", tags=["root"])
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to TrackUs API",
        "docs": "/docs",
        "health": "/health"
    }
