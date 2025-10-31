from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        resp: Response = await call_next(request)
        try:
            resp.headers.setdefault("X-Content-Type-Options", "nosniff")
            resp.headers.setdefault("X-Frame-Options", "DENY")
            resp.headers.setdefault("Referrer-Policy", "no-referrer")
            resp.headers.setdefault(
                "Permissions-Policy",
                "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
            )
            if request.method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
                resp.headers.setdefault("Cache-Control", "no-store")
            else:
                resp.headers.setdefault("Cache-Control", "no-cache, max-age=0")
        except Exception:
            pass
        return resp

