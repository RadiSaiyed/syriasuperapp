import json
import logging
from typing import Any, Dict

import redis

from .config import settings


log = logging.getLogger(__name__)


def _redis_client() -> redis.Redis | None:
    try:
        return redis.from_url(settings.REDIS_URL) if settings.REDIS_URL else None
    except Exception:
        return None


def notify(event: str, payload: Dict[str, Any]) -> None:
    mode = getattr(settings, "NOTIFY_MODE", "log")
    if mode == "redis":
        chan = getattr(settings, "NOTIFY_REDIS_CHANNEL", "agriculture.events")
        cli = _redis_client()
        if cli is None:
            log.warning("notify(redis): no client available; falling back to log")
        else:
            try:
                cli.publish(chan, json.dumps({"event": event, "data": payload}))
                return
            except Exception as e:
                log.warning("notify(redis) failed: %s", e)
    log.info("event=%s payload=%s", event, payload)

