from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from ..auth import get_current_user, get_db
from ..config import settings
from ..models import Entry, Reservation


router = APIRouter(prefix="/entries", tags=["entries"])


class StartReq(BaseModel):
    facility_id: str
    plate: str | None = None
    qr_code: str | None = None


class StartRes(BaseModel):
    id: str
    started_at: datetime
    source: str


@router.post("/start", response_model=StartRes)
def start(req: StartReq, db: Session = Depends(get_db), user=Depends(get_current_user)):
    res = None
    src = "lpr"
    if req.qr_code:
        res = db.query(Reservation).filter(Reservation.qr_code == req.qr_code, Reservation.status == "reserved").one_or_none()
        if not res:
            raise HTTPException(404, "qr_invalid")
        src = "qr"
    e = Entry(facility_id=req.facility_id, reservation_id=res.id if res else None, plate=req.plate)
    db.add(e)
    db.flush()
    if res:
        res.status = "checked_in"
    return StartRes(id=str(e.id), started_at=e.started_at, source=src)


class StopRes(BaseModel):
    id: str
    stopped_at: datetime
    price_cents: int
    payment_request_id: str | None = None


@router.post("/{eid}/stop", response_model=StopRes)
def stop(eid: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    e = db.get(Entry, eid)
    if not e or e.stopped_at is not None:
        raise HTTPException(404, "entry_invalid")
    from datetime import timedelta
    e.stopped_at = datetime.utcnow()
    dur_h = max(1, int(((e.stopped_at - e.started_at).total_seconds()) // 3600))
    e.price_cents = 4000 * dur_h * 100
    # Optional: create payment request for exit
    try:
        if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and (e.price_cents or 0) > 0:
            requester_phone = getattr(settings, "FEE_WALLET_PHONE", None)
            target_phone = getattr(user, "phone", None)
            if requester_phone and target_phone:
                payload_json = {
                    "from_phone": requester_phone,
                    "to_phone": target_phone,
                    "amount_cents": int(e.price_cents or 0),
                    "metadata": {"entry_id": str(e.id), "service": "parking_offstreet"},
                }
                from superapp_shared.internal_hmac import sign_internal_request_headers
                import httpx
                headers = sign_internal_request_headers(payload_json, settings.PAYMENTS_INTERNAL_SECRET, None)
                with httpx.Client(timeout=5.0) as client:
                    resp = client.post(f"{settings.PAYMENTS_BASE_URL}/internal/requests", headers=headers, json=payload_json)
                    if resp.status_code < 400:
                        e.payment_request_id = resp.json().get("id")
                        db.flush()
    except Exception:
        pass
    return StopRes(id=str(e.id), stopped_at=e.stopped_at, price_cents=e.price_cents or 0, payment_request_id=e.payment_request_id)
