import time
import threading
from typing import Any, Hashable, Optional
import json

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None

try:
    # Lazy import settings to avoid circulars at module import
    from ..config import settings  # type: ignore
except Exception:
    class _S:  # fallback
        CACHE_BACKEND = "memory"
        CACHE_REDIS_URL = "redis://localhost:6379/0"
    settings = _S()


class TTLCache:
    def __init__(self):
        self._data: dict[Hashable, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> Optional[Any]:
        now = time.time()
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at < now:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: Hashable, value: Any, ttl_secs: int) -> None:
        with self._lock:
            self._data[key] = (time.time() + float(ttl_secs), value)


class RedisCache:
    def __init__(self, url: str):
        self._url = url
        self._client = None
        try:
            if redis is not None:
                self._client = redis.from_url(url)
        except Exception:
            self._client = None

    def get(self, key: Hashable) -> Optional[Any]:
        if not self._client:
            return None
        try:
            raw = self._client.get(self._serialize_key(key))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def set(self, key: Hashable, value: Any, ttl_secs: int) -> None:
        if not self._client:
            return
        try:
            self._client.setex(self._serialize_key(key), int(ttl_secs), json.dumps(value, default=self._json_default))
        except Exception:
            pass

    @staticmethod
    def _serialize_key(key: Hashable) -> str:
        try:
            return json.dumps(key, sort_keys=True)
        except Exception:
            return str(key)

    @staticmethod
    def _json_default(o):
        try:
            return o.model_dump()
        except Exception:
            return str(o)


_cache: Any
if getattr(settings, "CACHE_BACKEND", "memory").lower() == "redis" and redis is not None:
    _cache = RedisCache(getattr(settings, "CACHE_REDIS_URL", "redis://redis:6379/0"))
else:
    _cache = TTLCache()

cache = _cache
