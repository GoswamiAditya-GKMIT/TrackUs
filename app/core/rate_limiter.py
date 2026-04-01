from fastapi_limiter.depends import RateLimiter as OriginalRateLimiter
from starlette.requests import Request
from starlette.responses import Response
from app.core.config import settings

class RateLimiter(OriginalRateLimiter):
    """
    Custom RateLimiter that respects the RATE_LIMIT_ENABLED setting.
    If disabled, it allows all requests to pass through without checking Redis.
    """
    async def __call__(self, request: Request, response: Response):
        if not settings.RATE_LIMIT_ENABLED:
            return
        
        await super().__call__(request, response)
