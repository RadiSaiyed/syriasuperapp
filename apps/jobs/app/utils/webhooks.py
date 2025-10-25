import hmac
import hashlib
import json
from typing import Any, Dict, List

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import WebhookEndpoint


def _sign(secret: str, ts: str, event: str, body: bytes) -> str:
    msg = (ts + event).encode("utf-8") + body
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def _send_batch(endpoints: List[WebhookEndpoint], event: str, payload: Dict[str, Any], timeout: float):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ts = str(int(__import__("time").time()))
    headers_base = {
        "Content-Type": "application/json",
        "X-Webhook-Event": event,
        "X-Webhook-Ts": ts,
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            for ep in endpoints:
                sig = _sign(ep.secret, ts, event, body)
                headers = headers_base | {"X-Webhook-Sign": sig}
                try:
                    client.post(ep.url, content=body, headers=headers)
                except Exception:
                    # Best-effort; no retries for now
                    pass
    except Exception:
        pass


def send_webhooks(db: Session, event: str, payload: Dict[str, Any], tasks=None) -> None:
    if str(getattr(settings, "WEBHOOK_ENABLED", "false")).lower() not in ("1", "true", "yes"):
        return
    endpoints = db.query(WebhookEndpoint).all()
    if not endpoints:
        return
    timeout = float(getattr(settings, "WEBHOOK_TIMEOUT_SECS", 3))
    if tasks is not None:
        tasks.add_task(_send_batch, endpoints, event, payload, timeout)
    else:
        _send_batch(endpoints, event, payload, timeout)

