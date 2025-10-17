from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import httpx

from ..auth import get_current_user, get_db
from ..config import settings
from sqlalchemy import select
from ..models import User, CarrierProfile, Load
from ..schemas import LoadOut, LoadsListOut


router = APIRouter(prefix="/loads", tags=["loads"])


def _to_out(l: Load) -> LoadOut:
    return LoadOut(
        id=str(l.id), status=l.status, shipper_user_id=str(l.shipper_user_id), carrier_id=str(l.carrier_id) if l.carrier_id else None, origin=l.origin, destination=l.destination, weight_kg=l.weight_kg, price_cents=l.price_cents, payment_request_id=l.payment_request_id, pod_url=l.pod_url
    )


def _get_carrier(db: Session, user: User) -> CarrierProfile:
    prof = db.query(CarrierProfile).filter(CarrierProfile.user_id == user.id).one_or_none()
    if prof is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Carrier not found")
    return prof


@router.post("/{load_id}/accept", response_model=LoadOut)
def accept(load_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    carrier = _get_carrier(db, user)
    l = db.execute(select(Load).where(Load.id == load_id).with_for_update()).scalars().first()
    if l is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load not found")
    if l.status != "posted":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not available")
    l.carrier_id = carrier.id
    l.status = "assigned"
    db.flush()
    return _to_out(l)


@router.get("/{load_id}", response_model=LoadOut)
def get_load(load_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Load, load_id)
    if l is None:
        raise HTTPException(status_code=404, detail="Load not found")
    # allow shipper or assigned carrier
    if l.shipper_user_id != user.id:
        if l.carrier_id:
            prof = db.query(CarrierProfile).filter(CarrierProfile.id == l.carrier_id).one_or_none()
            if not prof or prof.user_id != user.id:
                raise HTTPException(status_code=403, detail="Forbidden")
        else:
            raise HTTPException(status_code=403, detail="Forbidden")
    return _to_out(l)


@router.post("/{load_id}/pickup", response_model=LoadOut)
def pickup(load_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    carrier = _get_carrier(db, user)
    l = db.execute(select(Load).where(Load.id == load_id).with_for_update()).scalars().first()
    if l is None or l.carrier_id != carrier.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load not found")
    if l.status not in ("assigned",):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state")
    l.status = "picked_up"
    l.pickup_at = datetime.utcnow()
    db.flush()
    return _to_out(l)


@router.post("/{load_id}/in_transit", response_model=LoadOut)
def in_transit(load_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    carrier = _get_carrier(db, user)
    l = db.execute(select(Load).where(Load.id == load_id).with_for_update()).scalars().first()
    if l is None or l.carrier_id != carrier.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load not found")
    if l.status not in ("picked_up",):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state")
    l.status = "in_transit"
    db.flush()
    return _to_out(l)


@router.post("/{load_id}/deliver", response_model=LoadOut)
def deliver(load_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    carrier = _get_carrier(db, user)
    l = db.execute(select(Load).where(Load.id == load_id).with_for_update()).scalars().first()
    if l is None or l.carrier_id != carrier.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load not found")
    if l.status not in ("in_transit", "picked_up"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state")
    l.status = "delivered"
    l.delivered_at = datetime.utcnow()
    db.flush()

    # Payments request: from shipper user phone to carrier user phone
    payment_request_id = None
    try:
        if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and l.price_cents:
            shipper = db.get(User, l.shipper_user_id)
            carrier_user = db.get(User, carrier.user_id)
            payload_json = {"from_phone": shipper.phone, "to_phone": carrier_user.phone, "amount_cents": l.price_cents}
            from superapp_shared.internal_hmac import sign_internal_request_headers
            headers = sign_internal_request_headers(payload_json, settings.PAYMENTS_INTERNAL_SECRET, request.headers.get("X-Request-ID", ""))
            with httpx.Client(timeout=5.0) as client:
                r = client.post(
                    f"{settings.PAYMENTS_BASE_URL}/internal/requests",
                    headers=headers,
                    json=payload_json,
                )
                if r.status_code < 400:
                    payment_request_id = r.json().get("id")
            # Platform fee (carrier -> fee wallet)
            fee_bps = settings.PLATFORM_FEE_BPS
            if fee_bps and l.price_cents:
                fee = int((l.price_cents * fee_bps + 5000)//10000)
                if fee > 0:
                    fee_payload = {"from_phone": carrier_user.phone, "to_phone": settings.FEE_WALLET_PHONE, "amount_cents": fee}
                    from superapp_shared.internal_hmac import sign_internal_request_headers
                    fee_headers = sign_internal_request_headers(fee_payload, settings.PAYMENTS_INTERNAL_SECRET, request.headers.get("X-Request-ID", ""))
                    with httpx.Client(timeout=5.0) as client:
                        client.post(
                            f"{settings.PAYMENTS_BASE_URL}/internal/requests",
                            headers=fee_headers,
                            json=fee_payload,
                        )
    except Exception:
        pass
    if payment_request_id:
        l.payment_request_id = payment_request_id
        db.flush()
    return _to_out(l)


@router.post("/{load_id}/pod")
def add_pod(load_id: str, url: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    carrier = _get_carrier(db, user)
    l = db.get(Load, load_id)
    if l is None or l.carrier_id != carrier.id:
        raise HTTPException(status_code=404, detail="Load not found")
    l.pod_url = (url or "").strip()
    db.flush()
    return {"detail": "ok"}


@router.get("", response_model=LoadsListOut)
def my_loads(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Load)
    # return latest loads either as shipper or carrier
    if user.role == "carrier":
        prof = db.query(CarrierProfile).filter(CarrierProfile.user_id == user.id).one_or_none()
        if prof:
            q = q.filter(Load.carrier_id == prof.id)
        else:
            q = q.filter(Load.shipper_user_id == user.id)
    else:
        q = q.filter(Load.shipper_user_id == user.id)
    rows = q.order_by(Load.created_at.desc()).limit(100).all()
    return LoadsListOut(loads=[_to_out(l) for l in rows])
