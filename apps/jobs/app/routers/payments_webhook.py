import hmac
import hashlib
import json
from fastapi import APIRouter, Header, HTTPException, status

from ..config import settings


router = APIRouter(prefix="/payments", tags=["payments-webhook"])


def _verify(ts: str, event: str, body: bytes, sign: str) -> bool:
    secret = getattr(settings, "PAYMENTS_WEBHOOK_SECRET", None)
    if not secret:
        return False
    expect = hmac.new(secret.encode("utf-8"), (ts + event).encode("utf-8") + body, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(expect, sign)
    except Exception:
        return False


@router.post("/webhooks")
def receive_webhook(
    payload: dict,
    ts: str | None = Header(default=None, alias="X-Webhook-Ts"),
    event: str | None = Header(default=None, alias="X-Webhook-Event"),
    sign: str | None = Header(default=None, alias="X-Webhook-Sign"),
):
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if not ts or not event or not sign or not _verify(ts, event, raw, sign):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")
    # Jobs currently does not track payment state; accept and ack.
    return {"detail": "ok"}

