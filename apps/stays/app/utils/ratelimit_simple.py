import time
import threading
from typing import Optional
from fastapi import Request, Response, HTTPException, status
try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None
try:
    from ..config import settings  # type: ignore
except Exception:
    class _S:
        CACHE_REDIS_URL = "redis://localhost:6379/0"
        CACHE_BACKEND = "memory"
    settings = _S()


_lock = threading.Lock()
_buckets: dict[str, tuple[float, int]] = {}


def _key_for(request: Request, name: str) -> str:
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    return f"rl:{name}:{ip}:{ua[:32]}"


_redis_client = None
if getattr(settings, "CACHE_BACKEND", "memory").lower() == "redis" and redis is not None:
    try:
        _redis_client = redis.from_url(getattr(settings, "CACHE_REDIS_URL", "redis://localhost:6379/0"))
    except Exception:
        _redis_client = None


def _incr_redis(key: str, ttl: int = 60) -> int:
    if not _redis_client:
        return -1
    try:
        pipe = _redis_client.pipeline()
        pipe.incr(key, 1)
        pipe.expire(key, ttl)
        res = pipe.execute()
        return int(res[0]) if res and isinstance(res[0], (int,)) else 0
    except Exception:
        return -1


def rate_limit_dependency(limit_per_minute: int, name: str):
    def _dep(request: Request, response: Response):
        now = time.time()
        key = _key_for(request, name)
        # Try redis first
        if _redis_client is not None:
            new_count = _incr_redis(key, 60)
            if new_count != -1:
                if new_count > limit_per_minute:
                    # cannot reliably get TTL remaining without extra call; default 60
                    response.headers.setdefault("X-RateLimit-Limit", str(limit_per_minute))
                    response.headers.setdefault("X-RateLimit-Remaining", "0")
                    response.headers.setdefault("X-RateLimit-Reset", "60")
                    raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail={"code": "rate_limited", "retry_after": 60}, headers={"Retry-After": "60"})
                # set headers with approximate remaining/ reset
                response.headers.setdefault("X-RateLimit-Limit", str(limit_per_minute))
                response.headers.setdefault("X-RateLimit-Remaining", str(max(0, limit_per_minute - int(new_count))))
                response.headers.setdefault("X-RateLimit-Reset", "60")
                return None
        # Fallback to memory
        with _lock:
            reset_at, count = _buckets.get(key, (now + 60.0, 0))
            if now > reset_at:
                reset_at, count = (now + 60.0, 0)
            count += 1
            _buckets[key] = (reset_at, count)
            if count > limit_per_minute:
                retry_after = int(max(1, reset_at - now))
                response.headers.setdefault("X-RateLimit-Limit", str(limit_per_minute))
                response.headers.setdefault("X-RateLimit-Remaining", "0")
                response.headers.setdefault("X-RateLimit-Reset", str(retry_after))
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail={"code": "rate_limited", "retry_after": retry_after}, headers={"Retry-After": str(retry_after)})
            # set headers for successful pass
            response.headers.setdefault("X-RateLimit-Limit", str(limit_per_minute))
            response.headers.setdefault("X-RateLimit-Remaining", str(max(0, limit_per_minute - int(count))))
            response.headers.setdefault("X-RateLimit-Reset", str(int(max(1, reset_at - now))))
        return None
    return _dep
