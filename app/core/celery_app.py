from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    settings.APP_NAME,
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.modules.cleanup.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Beat Schedule
celery_app.conf.beat_schedule = {
    "cleanup-expired-tokens": {
        "task": "app.modules.cleanup.tasks.cleanup_expired_tokens",
        "schedule": crontab(minute="0", hour="*"),  # Every hour
    },
    "cleanup-unverified-users": {
        "task": "app.modules.cleanup.tasks.cleanup_unverified_users",
        "schedule": crontab(minute="0", hour="*/4"),  # Every 4 hours
    },
    "cleanup-soft-deleted-users": {
        "task": "app.modules.cleanup.tasks.cleanup_soft_deleted_users",
        "schedule": crontab(minute="0", hour="0"),  # Daily at midnight
    },
}
