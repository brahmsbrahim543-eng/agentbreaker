from fastapi import Request
from fastapi.responses import JSONResponse


class AgentBreakerError(Exception):
    status_code: int = 500
    error_type: str = "internal_error"

    def __init__(self, message: str = "An internal error occurred"):
        self.message = message
        super().__init__(self.message)


class NotFoundError(AgentBreakerError):
    status_code = 404
    error_type = "not_found"

    def __init__(self, resource: str = "Resource", identifier: str = ""):
        msg = f"{resource} {identifier} not found" if identifier else f"{resource} not found"
        super().__init__(msg)


class AuthenticationError(AgentBreakerError):
    status_code = 401
    error_type = "authentication_error"

    def __init__(self, message: str = "Invalid or missing credentials"):
        super().__init__(message)


class AuthorizationError(AgentBreakerError):
    status_code = 403
    error_type = "authorization_error"

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message)


class RateLimitError(AgentBreakerError):
    status_code = 429
    error_type = "rate_limit_exceeded"

    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s")


class DetectionError(AgentBreakerError):
    status_code = 500
    error_type = "detection_error"

    def __init__(self, message: str = "Detection engine error"):
        super().__init__(message)


class ValidationError(AgentBreakerError):
    status_code = 422
    error_type = "validation_error"


async def agentbreaker_exception_handler(request: Request, exc: AgentBreakerError) -> JSONResponse:
    headers = {}
    if isinstance(exc, RateLimitError):
        headers["Retry-After"] = str(exc.retry_after)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_type,
            "message": exc.message,
            "status_code": exc.status_code,
        },
        headers=headers,
    )
