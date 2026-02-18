"""
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import time

from app.core.config import settings
from app.db.base import import_models
from app.db.session import async_engine
from app.core.redis import init_redis, close_redis
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis

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
from app.modules.events.router import router as events_router
from app.modules.location.router import router as location_router
from app.modules.notifications.router import router as notifications_router
from app.realtime.pubsub import pubsub_manager
from app.realtime.manager import manager
from app.realtime.chat import chat_socket_handler, event_chat_socket_handler
from app.realtime.location import location_socket_handler
from app.realtime.notifications import notification_socket_handler
from app.core.celery_app import celery_app
from app.core.logging import setup_logging , log_request_middleware



setup_logging()

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

    if settings.RATE_LIMIT_ENABLED:
        redis_conn = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        await FastAPILimiter.init(redis_conn)
        logger.info("FastAPI Rate Limiter initialized")
    else:
        logger.info("FastAPI Rate Limiter disabled by configuration")

    logger.info(f"Celery app initialized: {celery_app.main}")
    logger.info(f"Registered Celery tasks: {list(celery_app.tasks.keys())}")

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

app.middleware("http")(log_request_middleware)

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
app.include_router(events_router, prefix="/api/v1")
app.include_router(location_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")

app.add_api_websocket_route("/chat/groups/{group_id}", chat_socket_handler)
app.add_api_websocket_route("/chat/events/{event_id}", event_chat_socket_handler)
app.add_api_websocket_route("/events/{event_id}/location", location_socket_handler)

app.add_api_websocket_route("/notifications", notification_socket_handler)





@app.get("/", tags=["root"])
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to TrackUs API",
        "docs": "/docs",
        "health": "/health"
    }
