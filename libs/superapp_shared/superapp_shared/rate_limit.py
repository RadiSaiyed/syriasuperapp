import time
import os
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None  # type: ignore


class SlidingWindowLimiter(BaseHTTPMiddleware):
    def __init__(self, app, limit_per_minute: int = 60, auth_boost: int = 2, exempt_otp: bool = True):
        super().__init__(app)
        self.window_seconds = 60
        self.limit_per_minute = limit_per_minute
        self.auth_boost = auth_boost
        self.exempt_otp = exempt_otp
        self.store: Dict[str, Deque[float]] = defaultdict(deque)

    def _key(self, request: Request) -> str:
        auth = request.headers.get("authorization")
        if auth:
            return f"token:{auth[-24:]}"
        client = request.client.host if request.client else "unknown"
        return f"ip:{client}"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Always bypass limiter for health checks to ensure constant-time responses
        if path == "/health":
            return await call_next(request)
        now = time.time()
        key = self._key(request)

        # allow runtime override via env
        try:
            base = int(os.getenv("RL_LIMIT_PER_MINUTE_OVERRIDE", str(self.limit_per_minute)))
        except Exception:
            base = self.limit_per_minute
        if path.startswith("/auth/"):
            base = min(base, 20)
        dev_env = (os.getenv("ENV", "dev").lower() == "dev")
        if self.exempt_otp and dev_env and path in ("/auth/request_otp", "/auth/verify_otp") and os.getenv("RL_EXEMPT_OTP", "true").lower() == "true":
            return await call_next(request)
        if request.headers.get("authorization"):
            try:
                boost = int(os.getenv("RL_AUTH_BOOST_OVERRIDE", str(self.auth_boost)))
            except Exception:
                boost = self.auth_boost
            base *= boost

        dq = self.store[key]
        while dq and now - dq[0] > self.window_seconds:
            dq.popleft()
        if len(dq) >= base:
            retry_after = max(1, int(self.window_seconds - (now - dq[0])))
            return JSONResponse(status_code=429, content={"error": {"code": "rate_limited", "message": "Too many requests", "details": {"retry_after": retry_after}}}, headers={"Retry-After": str(retry_after)})
        dq.append(now)
        return await call_next(request)


class RedisRateLimiter(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str, limit_per_minute: int = 60, auth_boost: int = 2, prefix: str = "ratelimit", exempt_otp: bool = True):
        super().__init__(app)
        self.redis = self._connect(redis_url)
        self.limit_per_minute = limit_per_minute
        self.auth_boost = auth_boost
        self.prefix = prefix
        self.exempt_otp = exempt_otp

    def _connect(self, url: str):
        if redis is None:
            return None
        try:
            return redis.from_url(url, decode_responses=True)
        except Exception:
            return None

    def _key(self, request: Request) -> str:
        auth = request.headers.get("authorization")
        if auth:
            return f"{self.prefix}:token:{auth[-24:]}"
        client = request.client.host if request.client else "unknown"
        return f"{self.prefix}:ip:{client}"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Always bypass limiter for health checks to ensure constant-time responses
        if path == "/health":
            return await call_next(request)
        try:
            base = int(os.getenv("RL_LIMIT_PER_MINUTE_OVERRIDE", str(self.limit_per_minute)))
        except Exception:
            base = self.limit_per_minute
        if path.startswith("/auth/"):
            base = min(base, 20)
        if request.headers.get("authorization"):
            try:
                boost = int(os.getenv("RL_AUTH_BOOST_OVERRIDE", str(self.auth_boost)))
            except Exception:
                boost = self.auth_boost
            base *= boost

        dev_env = (os.getenv("ENV", "dev").lower() == "dev")
        if self.exempt_otp and dev_env and path in ("/auth/request_otp", "/auth/verify_otp") and os.getenv("RL_EXEMPT_OTP", "true").lower() == "true":
            return await call_next(request)

        now = int(time.time())
        window = now // 60
        key = f"{self._key(request)}:{window}"
        try:
            if self.redis is None:
                # Fail-open: no Redis
                return await call_next(request)
            count = self.redis.incr(key)
            if count == 1:
                self.redis.expire(key, 70)
            if count > base:
                retry_after = 60 - (now % 60)
                return JSONResponse(status_code=429, content={"error": {"code": "rate_limited", "message": "Too many requests", "details": {"retry_after": retry_after}}}, headers={"Retry-After": str(retry_after)})
        except Exception:
            # fail open
            return await call_next(request)
        return await call_next(request)
