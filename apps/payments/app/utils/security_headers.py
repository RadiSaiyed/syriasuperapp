from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds a set of conservative security headers appropriate for APIs.

    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - Referrer-Policy: no-referrer
    - Permissions-Policy: restrict powerful features
    - Cache-Control: no-store for non-GETs, reasonable for GETs
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        # Core headers
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # Disable powerful browser features by default (API surface)
        response.headers.setdefault(
            "Permissions-Policy",
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
        )
        # Caching: prevent caching of state-changing responses
        if request.method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
            response.headers.setdefault("Cache-Control", "no-store")
        else:
            # idempotent GETs — keep short, safe cache policy to aid proxies without leaking sensitive data
            response.headers.setdefault("Cache-Control", "no-cache, max-age=0")
        return response

