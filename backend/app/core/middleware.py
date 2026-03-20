import time

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        await logger.ainfo(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            client=request.client.host if request.client else None,
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_getter, max_requests: int = 100):
        super().__init__(app)
        self.redis_getter = redis_getter
        self.max_requests = max_requests

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for health checks and WebSocket
        if request.url.path in ("/health", "/docs", "/openapi.json") or request.url.path.startswith("/api/v1/ws"):
            return await call_next(request)

        # Identify by API key first, then IP
        api_key = request.headers.get("x-api-key")
        client_ip = request.client.host if request.client else "unknown"
        identifier = f"ratelimit:{api_key or client_ip}"

        try:
            redis = self.redis_getter()
            current = await redis.incr(identifier)
            if current == 1:
                await redis.expire(identifier, 60)

            if current > self.max_requests:
                from app.core.exceptions import RateLimitError
                raise RateLimitError(retry_after=60)
        except Exception as exc:
            # Redis unavailable — allow request through
            # Catches redis.exceptions.ConnectionError, RuntimeError, OSError, etc.
            if "RateLimitError" in type(exc).__name__:
                raise
            pass

        return await call_next(request)
