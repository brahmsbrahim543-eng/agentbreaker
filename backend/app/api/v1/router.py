"""Main API v1 router -- includes all sub-routers with proper prefixes and tags."""

from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.projects import router as projects_router
from app.api.v1.routes.api_keys import router as api_keys_router
from app.api.v1.routes.agents import router as agents_router
from app.api.v1.routes.ingest import router as ingest_router
from app.api.v1.routes.incidents import router as incidents_router
from app.api.v1.routes.analytics import router as analytics_router
from app.api.v1.routes.settings import router as settings_router
from app.api.v1.routes.playground import router as playground_router
from app.api.v1.routes.ws import router as ws_router
from app.api.v1.routes.integrations import router as integrations_router
from app.api.v1.routes.billing import router as billing_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(api_keys_router)
api_router.include_router(agents_router)
api_router.include_router(ingest_router)
api_router.include_router(incidents_router)
api_router.include_router(analytics_router)
api_router.include_router(settings_router)
api_router.include_router(playground_router)
api_router.include_router(ws_router)
api_router.include_router(integrations_router)
api_router.include_router(billing_router)
