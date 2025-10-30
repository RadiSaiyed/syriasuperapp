from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx

from ..auth import get_current_user, get_db
from ..config import settings
from ..models import Reservation, Entry


router = APIRouter(prefix="/operator", tags=["operator"])


@router.get("/payment_status")
def payment_status(request_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Lookup local mapping on reservations/entries
    res = (
        db.query(Reservation)
        .filter(Reservation.payment_request_id == request_id)
        .one_or_none()
    )
    ent = None if res else db.query(Entry).filter(Entry.payment_request_id == request_id).one_or_none()

    local = {
        "scope": ("reservation" if res else ("entry" if ent else None)),
        "reservation_id": str(res.id) if res else None,
        "entry_id": str(ent.id) if ent else None,
        "transfer_id": (res.payment_transfer_id if res else (ent.payment_transfer_id if ent else None)),
    }

    # Try remote Payments status if configured
    remote = None
    if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET:
        try:
            from superapp_shared.internal_hmac import sign_internal_request_headers
            headers = sign_internal_request_headers({"id": request_id}, settings.PAYMENTS_INTERNAL_SECRET)
            url = f"{settings.PAYMENTS_BASE_URL.rstrip('/')}/internal/requests/{request_id}"
            with httpx.Client(timeout=3.5) as client:
                r = client.get(url, headers=headers)
                if r.status_code < 400:
                    remote = r.json()
        except Exception:
            remote = None

    if not local["scope"] and not remote:
        raise HTTPException(status_code=404, detail="request_not_found")
    return {"local": local, "remote": remote}

