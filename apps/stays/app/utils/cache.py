import time
import threading
from typing import Any, Hashable, Optional


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


cache = TTLCache()

