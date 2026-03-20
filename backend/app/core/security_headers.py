"""Enterprise security headers middleware.

Adds OWASP-recommended security headers to every HTTP response to prevent:
- XSS (Content-Security-Policy, X-XSS-Protection)
- Clickjacking (X-Frame-Options)
- MIME sniffing (X-Content-Type-Options)
- Information leakage (Server header removal)
- Protocol downgrade (Strict-Transport-Security)
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject OWASP-recommended security headers into every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS filter (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict powerful browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )

        # Prevent caching of sensitive API responses
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"

        # HSTS — enforce HTTPS for 1 year (including subdomains)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # Content-Security-Policy — API-only baseline
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )

        # Remove server identification header to reduce fingerprinting surface
        if "server" in response.headers:
            del response.headers["server"]

        return response
