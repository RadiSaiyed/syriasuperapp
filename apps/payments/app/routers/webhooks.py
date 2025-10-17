import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
import httpx
import hmac, hashlib, json

from ..auth import get_current_user, get_db
from ..models import User, WebhookEndpoint, WebhookDelivery
from prometheus_client import Counter
from sqlalchemy import or_, select


router = APIRouter(prefix="/webhooks", tags=["webhooks"])

DELIV_COUNTER = Counter("payments_webhook_deliveries_total", "Webhook deliveries", ["status"]) 
ATTEMPT_COUNTER = Counter("payments_webhook_attempts_total", "Webhook attempts", ["result"]) 


def _post_webhook(url: str, secret: str, payload: dict, delivery_id: str | None = None) -> None:
    """Send webhook to URL. Supports app://echo shortcut in tests."""
    from urllib.parse import urlparse
    from ..config import settings
    parsed = urlparse(url)
    if parsed.scheme == 'app' and url.startswith("app://echo"):
        return
    # Only allow https in non-dev
    if settings.ENV != 'dev' and parsed.scheme != 'https':
        raise RuntimeError('insecure webhook url')
    ts = str(int(datetime.utcnow().timestamp()))
    body = json.dumps(payload, separators=(",", ":")).encode()
    sign = hmac.new(secret.encode(), (ts + payload.get("type", "")).encode() + body, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Ts": ts,
        "X-Webhook-Event": payload.get("type", "event"),
        "X-Webhook-Sign": sign,
        "X-Delivery-ID": delivery_id or "",
        "User-Agent": "Payments-Webhooks/0.1",
    }
    with httpx.Client(timeout=5.0) as client:
        r = client.post(url, headers=headers, content=body)
        r.raise_for_status()


def _dispatch_async(delivery_id: str, url: str, secret: str, payload: dict):
    try:
        _post_webhook(url, secret, payload, delivery_id)
    except Exception:
        pass


@router.post("/endpoints")
def create_endpoint(
    url: str,
    secret: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.is_merchant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Merchant only")
    ep = WebhookEndpoint(user_id=user.id, url=url.strip(), secret=secret.strip(), active=True)
    db.add(ep)
    db.flush()
    return {"id": str(ep.id), "url": ep.url, "active": ep.active}


@router.get("/endpoints")
def list_endpoints(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    eps = db.query(WebhookEndpoint).filter(WebhookEndpoint.user_id == user.id).order_by(WebhookEndpoint.created_at.desc()).all()
    return [{"id": str(e.id), "url": e.url, "active": e.active, "created_at": e.created_at.isoformat() + "Z"} for e in eps]


@router.post("/test")
def send_test_event(background: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    eps = db.query(WebhookEndpoint).filter(WebhookEndpoint.user_id == user.id, WebhookEndpoint.active == True).all()  # noqa: E712
    payload = {"type": "webhook.test", "data": {"user": str(user.id)}}
    created = []
    for e in eps:
        d = WebhookDelivery(endpoint_id=e.id, event_type=payload["type"], payload=payload, status="pending")
        db.add(d)
        db.flush()
        background.add_task(_dispatch_async, str(d.id), e.url, e.secret, payload)
        created.append(str(d.id))
        try:
            DELIV_COUNTER.labels("created").inc()
        except Exception:
            pass
    return {"deliveries": created}


@router.get("/deliveries")
def list_deliveries(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    eps = select(WebhookEndpoint.id).where(WebhookEndpoint.user_id == user.id)
    ds = (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.endpoint_id.in_(eps))
        .order_by(WebhookDelivery.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": str(d.id),
            "endpoint_id": str(d.endpoint_id),
            "event_type": d.event_type,
            "status": d.status,
            "attempt_count": d.attempt_count,
            "created_at": d.created_at.isoformat() + "Z",
        }
        for d in ds
    ]


def _should_attempt(created_at: datetime, attempt_count: int) -> bool:
    base = int(os.getenv("WEBHOOK_BASE_DELAY_SECS", "2"))
    factor = int(os.getenv("WEBHOOK_BACKOFF_FACTOR", "2"))
    if attempt_count == 0:
        return True
    delay = base * (factor ** (attempt_count - 1))
    return datetime.utcnow() >= created_at + timedelta(seconds=delay)


def _process_once(db: Session, limit: int = 20):
    max_attempts = int(os.getenv("WEBHOOK_MAX_ATTEMPTS", "5"))
    now = datetime.utcnow()
    pending = (
        db.query(WebhookDelivery)
        .filter(
            WebhookDelivery.status == "pending",
            or_(WebhookDelivery.next_attempt_at == None, WebhookDelivery.next_attempt_at <= now),  # noqa: E711
        )
        .order_by(WebhookDelivery.created_at.asc())
        .limit(limit)
        .all()
    )
    for d in pending:
        if d.attempt_count >= max_attempts:
            d.status = "failed"
            continue
        # guard in case next_attempt_at is missing
        if not _should_attempt(d.last_attempt_at or d.created_at, d.attempt_count):
            continue
        ep = db.get(WebhookEndpoint, d.endpoint_id)
        if ep is None:
            d.status = "failed"
            d.last_error = "endpoint_missing"
            d.last_attempt_at = datetime.utcnow()
            d.next_attempt_at = None
            try:
                ATTEMPT_COUNTER.labels("error").inc()
                DELIV_COUNTER.labels("failed").inc()
            except Exception:
                pass
            db.flush()
            continue
        try:
            _post_webhook(ep.url, ep.secret, d.payload, str(d.id))
            d.status = "delivered"
            d.delivered_at = datetime.utcnow()
            d.last_attempt_at = d.delivered_at
            d.next_attempt_at = None
            try:
                ATTEMPT_COUNTER.labels("success").inc()
                DELIV_COUNTER.labels("delivered").inc()
            except Exception:
                pass
        except Exception as e:
            d.attempt_count += 1
            d.last_error = str(e)[:500]
            d.last_attempt_at = datetime.utcnow()
            # schedule next attempt with exponential backoff
            base = int(os.getenv("WEBHOOK_BASE_DELAY_SECS", "2"))
            factor = int(os.getenv("WEBHOOK_BACKOFF_FACTOR", "2"))
            delay = base * (factor ** max(d.attempt_count - 1, 0))
            d.next_attempt_at = d.last_attempt_at + timedelta(seconds=delay)
            try:
                ATTEMPT_COUNTER.labels("error").inc()
            except Exception:
                pass
            if d.attempt_count >= max_attempts:
                d.status = "failed"
                # Optional: auto-disable misbehaving endpoint
                disable_after = int(os.getenv("WEBHOOK_DISABLE_AFTER_FAILS", "0"))
                if disable_after and d.attempt_count >= disable_after:
                    ep.active = False
                try:
                    DELIV_COUNTER.labels("failed").inc()
                except Exception:
                    pass
        db.flush()


@router.post("/process_once")
def process_once(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Dev‑only helper
    from ..config import settings
    if settings.ENV != "dev":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    _process_once(db)
    return {"detail": "ok"}


@router.post("/process_pending")
def process_pending(user: User = Depends(get_current_user), db: Session = Depends(get_db), max_cycles: int = 5, batch_size: int = 50):
    # Dev helper to sweep all due pending deliveries with backoff consideration.
    from ..config import settings
    if settings.ENV != "dev":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    cycles = 0
    while cycles < max_cycles:
        _process_once(db, limit=batch_size)
        # stop if no more due deliveries
        due = db.query(WebhookDelivery).filter(WebhookDelivery.status == "pending").count()
        if due == 0:
            break
        cycles += 1
    return {"detail": "ok", "cycles": cycles}


@router.post("/deliveries/{delivery_id}/requeue")
def requeue_delivery(delivery_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.get(WebhookDelivery, delivery_id)
    if d is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # Ensure ownership
    ep = db.get(WebhookEndpoint, d.endpoint_id)
    if ep is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint missing")
    if ep.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    d.status = "pending"
    d.attempt_count = 0
    d.last_error = None
    db.flush()
    return {"detail": "requeued"}
