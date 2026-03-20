"""Honeypot endpoints — detect automated scanners and vulnerability bots.

These routes impersonate common attack targets (WordPress admin panels,
phpMyAdmin, .env files, debug consoles).  Any request that hits them is
almost certainly a scanner or an attacker, so we log the source details
for security monitoring and return a convincing-but-harmless response.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, PlainTextResponse

logger = structlog.get_logger("security.honeypot")

router = APIRouter(tags=["honeypot"], include_in_schema=False)

# Paths that real users would never visit on an API server
_TRAP_PATHS: list[str] = [
    "/admin",
    "/wp-admin",
    "/wp-login.php",
    "/phpmyadmin",
    "/.env",
    "/.git/config",
    "/api/debug",
    "/api/internal",
    "/config.json",
    "/server-status",
    "/actuator",
    "/actuator/health",
    "/debug/vars",
    "/console",
]


async def _log_and_respond(request: Request):
    """Log scanner details and return a plausible decoy response."""
    client_ip = request.client.host if request.client else "unknown"
    await logger.awarn(
        "honeypot_triggered",
        path=str(request.url.path),
        method=request.method,
        ip=client_ip,
        user_agent=request.headers.get("user-agent", ""),
        referer=request.headers.get("referer", ""),
        query=str(request.query_params),
    )

    # Return 404 — a real service would, too.  Don't give away
    # that we know they're scanning.
    return JSONResponse(
        status_code=404,
        content={"detail": "Not found"},
    )


# Register every trap path for GET and POST
for _path in _TRAP_PATHS:
    router.add_api_route(
        _path,
        _log_and_respond,
        methods=["GET", "POST", "PUT", "DELETE"],
        response_class=JSONResponse,
    )


# Catch-all for common file-extension probes (e.g. /backup.sql, /dump.sql.gz)
@router.get("/{full_path:path}.sql")
@router.get("/{full_path:path}.sql.gz")
@router.get("/{full_path:path}.bak")
@router.get("/{full_path:path}.tar.gz")
@router.get("/{full_path:path}.zip")
async def _file_probe_trap(request: Request, full_path: str):
    return await _log_and_respond(request)
