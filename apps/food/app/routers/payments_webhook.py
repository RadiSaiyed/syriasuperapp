import hmac
import hashlib
import json
from fastapi import APIRouter, Header, HTTPException, status, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Order


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
    db: Session = Depends(get_db),
    ts: str | None = Header(default=None, alias="X-Webhook-Ts"),
    event: str | None = Header(default=None, alias="X-Webhook-Event"),
    sign: str | None = Header(default=None, alias="X-Webhook-Sign"),
):
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if not ts or not event or not sign or not _verify(ts, event, raw, sign):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")
    if payload.get("type") in ("requests.accept", "requests.accepted"):
        data = payload.get("data", {})
        pr_id = data.get("id")
        transfer_id = data.get("transfer_id")
        if pr_id:
            o = db.query(Order).filter(Order.payment_request_id == pr_id).one_or_none()
            if o is not None and o.status == "created":
                o.status = "accepted"
                if transfer_id:
                    o.payment_transfer_id = transfer_id
                db.flush()
    elif payload.get("type") in ("refunds.create",):
        data = payload.get("data", {})
        original = data.get("original")
        if original:
            rows = db.query(Order).filter(Order.payment_transfer_id == original).all()
            for o in rows:
                o.refund_status = "completed"
            if rows:
                db.flush()
    return {"detail": "ok"}
