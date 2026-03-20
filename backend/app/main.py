import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import AgentBreakerError, agentbreaker_exception_handler
from app.core.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from app.core.redis import close_redis, get_redis_pool, init_redis
from app.core.security_headers import SecurityHeadersMiddleware

# Maximum request body size: 10 MB
MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds the configured limit."""

    def __init__(self, app, max_bytes: int = MAX_REQUEST_BODY_BYTES):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": f"Request body too large. Maximum allowed: {self.max_bytes} bytes"
                },
            )
        return await call_next(request)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Startup — create tables if using SQLite (dev mode)
    from app.core.database import Base
    import app.models  # noqa: F401 — ensure all models registered with Base

    if settings.DATABASE_URL.startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await logger.ainfo("database_tables_created", mode="sqlite_dev")
    else:
        async with engine.begin() as conn:
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
    await logger.ainfo("database_connected", url=settings.DATABASE_URL.split("@")[-1])

    try:
        redis = await init_redis()
        await redis.ping()
        await logger.ainfo("redis_connected", url=settings.REDIS_URL)
    except Exception as e:
        await logger.awarn("redis_unavailable", error=str(e))

    await logger.ainfo("agentbreaker_started", version="1.0.0")

    # Start background simulator in dev mode
    if settings.DATABASE_URL.startswith("sqlite") and settings.SIMULATOR_ENABLED:
        from app.services.simulator import start_simulator
        asyncio.create_task(start_simulator())

    yield

    # Shutdown
    from app.services.simulator import stop_simulator
    await stop_simulator()
    await close_redis()
    await engine.dispose()
    await logger.ainfo("agentbreaker_stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AgentBreaker API",
        description="Detect and kill runaway AI agents in real-time",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Exception handler
    app.add_exception_handler(AgentBreakerError, agentbreaker_exception_handler)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security middleware (outermost runs first — order matters)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=MAX_REQUEST_BODY_BYTES)

    # Custom middleware
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware, redis_getter=get_redis_pool, max_requests=settings.RATE_LIMIT_PER_MINUTE)

    # Routes
    from app.api.v1.router import api_router
    app.include_router(api_router, prefix=f"/api/{settings.API_VERSION}")

    # Honeypot routes (catch scanner/bot probes)
    from app.core.honeypot import router as honeypot_router
    app.include_router(honeypot_router)

    @app.get("/health")
    async def health():
        db_status = "connected"
        redis_status = "connected"

        try:
            async with engine.begin() as conn:
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))
        except Exception:
            db_status = "disconnected"

        try:
            redis = get_redis_pool()
            await redis.ping()
        except Exception:
            redis_status = "disconnected"

        status = "healthy" if db_status == "connected" else "degraded"
        return {
            "status": status,
            "version": "1.0.0",
            "database": db_status,
            "redis": redis_status,
        }

    # Serve frontend static build (production mode)
    import os
    frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
    if os.path.isdir(frontend_dist):
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import FileResponse

        # Serve static assets (JS, CSS, images)
        assets_dir = os.path.join(frontend_dist, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        # Catch-all: serve index.html for SPA routing
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            file_path = os.path.join(frontend_dist, full_path)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            return FileResponse(os.path.join(frontend_dist, "index.html"))

    return app


app = create_app()
