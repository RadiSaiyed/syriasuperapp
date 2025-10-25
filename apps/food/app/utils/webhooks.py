import hmac
import hashlib
import json
from typing import Any, Dict, List

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import WebhookEndpoint, WebhookDelivery
from ..database import SessionLocal


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
                    pass
    except Exception:
        pass


def send_webhooks(db: Session, event: str, payload: Dict[str, Any], tasks=None) -> None:
    if str(getattr(settings, "WEBHOOK_ENABLED", "false")).lower() not in ("1", "true", "yes"):
        return
    endpoints = db.query(WebhookEndpoint).all()
    if not endpoints:
        return
    # Enqueue deliveries for reliability
    body = json.dumps(payload, separators=(",", ":"))
    for ep in endpoints:
        db.add(WebhookDelivery(endpoint_id=ep.id, event=event, payload_json=body, status="pending", attempts=0))
    db.flush()
    # Kick a best-effort immediate attempt in background if available
    if tasks is not None:
        tasks.add_task(process_pending_once)


def process_pending_once() -> None:
    if str(getattr(settings, "WEBHOOK_ENABLED", "false")).lower() not in ("1", "true", "yes"):
        return
    try:
        db: Session = SessionLocal()
    except Exception:
        return
    try:
        eps = {str(ep.id): ep for ep in db.query(WebhookEndpoint).all()}
        pend = (
            db.query(WebhookDelivery)
            .filter(WebhookDelivery.status == "pending", WebhookDelivery.attempts < int(getattr(settings, "WEBHOOK_MAX_ATTEMPTS", 5)))
            .order_by(WebhookDelivery.created_at.asc())
            .limit(50)
            .all()
        )
        timeout = float(getattr(settings, "WEBHOOK_TIMEOUT_SECS", 3))
        now_ts = str(int(__import__("time").time()))
        with httpx.Client(timeout=timeout) as client:
            for d in pend:
                ep = eps.get(str(d.endpoint_id))
                if not ep:
                    d.status = "failed"; d.last_error = "missing endpoint"; d.attempts += 1
                    continue
                try:
                    body = d.payload_json.encode("utf-8")
                    sig = _sign(ep.secret, now_ts, d.event, body)
                    headers = {
                        "Content-Type": "application/json",
                        "X-Webhook-Event": d.event,
                        "X-Webhook-Ts": now_ts,
                        "X-Webhook-Sign": sig,
                    }
                    r = client.post(ep.url, content=body, headers=headers)
                    if r.status_code < 300:
                        d.status = "sent"
                    else:
                        d.status = "pending"
                        d.last_error = f"http {r.status_code}"
                    d.attempts += 1
                except Exception as e:
                    d.attempts += 1
                    d.status = "pending" if d.attempts < int(getattr(settings, "WEBHOOK_MAX_ATTEMPTS", 5)) else "failed"
                    d.last_error = e.__class__.__name__
        db.flush()
    except Exception:
        pass
    finally:
        try:
            db.commit()
        except Exception:
            db.rollback()
        db.close()
