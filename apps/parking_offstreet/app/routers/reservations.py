from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
from ..auth import get_current_user, get_db
from ..config import settings
from ..models import Reservation


router = APIRouter(prefix="/reservations", tags=["reservations"])


class CreateReq(BaseModel):
    facility_id: str
    from_ts: datetime
    to_ts: datetime


class CreateRes(BaseModel):
    id: str
    qr_code: str
    price_cents: int
    status: str
    payment_request_id: str | None = None


@router.post("/", response_model=CreateRes)
def create(req: CreateReq, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if req.from_ts >= req.to_ts:
        raise HTTPException(400, "invalid_time")
    # MVP fixed price: 5000 SYP per hour
    dur_h = max(1, int((req.to_ts - req.from_ts).total_seconds() // 3600))
    price = 5000 * dur_h * 100
    qr = secrets.token_urlsafe(24)
    r = Reservation(user_id=user.id, facility_id=req.facility_id, from_ts=req.from_ts, to_ts=req.to_ts, price_cents=price, status="reserved", qr_code=qr)
    db.add(r)
    db.flush()
    # Optional: create payment request via Payments service
    try:
        if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and price > 0:
            requester_phone = getattr(settings, "FEE_WALLET_PHONE", None)
            target_phone = getattr(user, "phone", None)
            if requester_phone and target_phone:
                payload_json = {
                    "from_phone": requester_phone,
                    "to_phone": target_phone,
                    "amount_cents": int(price),
                    "metadata": {"reservation_id": str(r.id), "service": "parking_offstreet"},
                }
                from superapp_shared.internal_hmac import sign_internal_request_headers
                import httpx
                headers = sign_internal_request_headers(payload_json, settings.PAYMENTS_INTERNAL_SECRET, None)
                with httpx.Client(timeout=5.0) as client:
                    resp = client.post(f"{settings.PAYMENTS_BASE_URL}/internal/requests", headers=headers, json=payload_json)
                    if resp.status_code < 400:
                        r.payment_request_id = resp.json().get("id")
                        db.flush()
    except Exception:
        pass
    return CreateRes(id=str(r.id), qr_code=r.qr_code, price_cents=price, status=r.status, payment_request_id=r.payment_request_id)
