from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request, Body
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from ..auth import get_db, get_current_user
from ..config import settings
from ..models import Partner, PartnerDispatch, PartnerDriverMap, Ride, Driver, DriverLocation
from ..schemas import PartnerRegisterIn, DispatchCreateIn, DispatchOut, RideStatusWebhookIn, DriverLocationWebhookIn
from superapp_shared.internal_hmac import verify_internal_hmac_with_replay
from pydantic import BaseModel


router = APIRouter(prefix="/partners", tags=["partners"])


def _partner_by_key(db: Session, key_id: str) -> Partner:
    p = db.query(Partner).filter(Partner.key_id == key_id, Partner.active == True).one_or_none()  # noqa: E712
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    return p


@router.post("/dev/register")
def dev_register_partner(payload: PartnerRegisterIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    # DEV only simple guard
    if settings.ENV.lower() != "dev":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    # Minimal authorization: any authenticated user in dev can register test partner
    existing = db.query(Partner).filter(Partner.key_id == payload.key_id).one_or_none()
    if existing:
        existing.name = payload.name
        existing.secret = payload.secret
        existing.active = True
        db.flush()
        return {"id": str(existing.id), "detail": "updated"}
    p = Partner(name=payload.name, key_id=payload.key_id, secret=payload.secret, active=True)
    db.add(p)
    db.flush()
    return {"id": str(p.id), "detail": "created"}


class DevMapDriverIn(BaseModel):
    partner_key_id: str
    external_driver_id: str
    driver_phone: str


@router.post("/dev/map_driver")
def dev_map_driver(
    payload: DevMapDriverIn | None = Body(default=None),
    partner_key_id: str | None = None,
    external_driver_id: str | None = None,
    driver_phone: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if settings.ENV.lower() != "dev":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    # Accept either JSON body or query params for convenience in dev
    if payload is not None:
        partner_key_id = payload.partner_key_id
        external_driver_id = payload.external_driver_id
        driver_phone = payload.driver_phone
    if not partner_key_id or not external_driver_id or not driver_phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing parameters")
    partner = _partner_by_key(db, partner_key_id)
    # Resolve internal driver by phone
    from ..models import User as _User, Driver as _Driver
    u = db.query(_User).filter(_User.phone == driver_phone).one_or_none()
    if u is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")
    drv = db.query(_Driver).filter(_Driver.user_id == u.id).one_or_none()
    if drv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="driver_not_found")
    mapping = db.query(PartnerDriverMap).filter(PartnerDriverMap.partner_id == partner.id, PartnerDriverMap.external_driver_id == external_driver_id).one_or_none()
    if mapping is None:
        mapping = PartnerDriverMap(partner_id=partner.id, external_driver_id=external_driver_id, driver_id=drv.id)
        db.add(mapping)
    else:
        mapping.driver_id = drv.id
    db.flush()
    return {"detail": "ok"}


@router.post("/dispatch", response_model=DispatchOut)
def create_dispatch(payload: DispatchCreateIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    # Any authenticated user can trigger dispatch for now (would be ops/dispatcher in prod)
    ride = db.get(Ride, payload.ride_id)
    if ride is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    partner = _partner_by_key(db, payload.partner_key_id)
    ext_id = payload.external_trip_id or f"{partner.key_id}-{ride.id}"
    existing = db.query(PartnerDispatch).filter(PartnerDispatch.partner_id == partner.id, PartnerDispatch.external_trip_id == ext_id).one_or_none()
    if existing:
        d = existing
    else:
        d = PartnerDispatch(ride_id=ride.id, partner_id=partner.id, external_trip_id=ext_id, status="sent")
        db.add(d)
        db.flush()
    return DispatchOut(
        id=str(d.id),
        ride_id=str(d.ride_id),
        partner_key_id=partner.key_id,
        external_trip_id=d.external_trip_id,
        status=d.status,
        created_at=d.created_at.isoformat() + "Z",
        updated_at=d.updated_at.isoformat() + "Z",
    )


def _verify_hmac(payload: dict, ts: str | None, sign: str | None, secret: str) -> None:
    if not ts or not sign:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="missing_signature")
    ok = verify_internal_hmac_with_replay(ts, payload, sign, secret)
    if not ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="bad_signature")


@router.post("/{partner_key_id}/webhooks/ride_status")
def webhook_ride_status(
    partner_key_id: str,
    payload: RideStatusWebhookIn,
    request: Request,
    db: Session = Depends(get_db),
    ts: str | None = Header(default=None, alias="X-Internal-Ts"),
    sign: str | None = Header(default=None, alias="X-Internal-Sign"),
):
    partner = _partner_by_key(db, partner_key_id)
    # Verify HMAC
    _verify_hmac(payload.model_dump(), ts, sign, partner.secret)
    # Locate dispatch
    d = db.query(PartnerDispatch).filter(PartnerDispatch.partner_id == partner.id, PartnerDispatch.external_trip_id == payload.external_trip_id).one_or_none()
    if d is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dispatch_not_found")
    ride = db.get(Ride, d.ride_id)
    if ride is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ride_not_found")
    now = datetime.now(timezone.utc)
    status_in = payload.status.lower()
    if status_in == "accepted":
        if ride.status in ("requested", "assigned"):
            ride.status = "accepted"
        d.status = "accepted"
    elif status_in == "enroute":
        ride.status = "enroute"
        ride.started_at = ride.started_at or now
        d.status = "enroute"
    elif status_in == "completed":
        ride.status = "completed"
        ride.completed_at = now
        if payload.final_fare_cents is not None:
            ride.final_fare_cents = payload.final_fare_cents
        d.status = "completed"
    elif status_in == "canceled":
        # If partner cancels, put ride back for reassignment
        ride.status = "requested"
        d.status = "canceled"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_status")
    d.updated_at = now
    db.flush()
    return {"detail": "ok"}


@router.post("/{partner_key_id}/webhooks/driver_location")
def webhook_driver_location(
    partner_key_id: str,
    payload: DriverLocationWebhookIn,
    request: Request,
    db: Session = Depends(get_db),
    ts: str | None = Header(default=None, alias="X-Internal-Ts"),
    sign: str | None = Header(default=None, alias="X-Internal-Sign"),
):
    partner = _partner_by_key(db, partner_key_id)
    _verify_hmac(payload.model_dump(), ts, sign, partner.secret)
    # Find mapped driver
    mapping = db.query(PartnerDriverMap).filter(PartnerDriverMap.partner_id == partner.id, PartnerDriverMap.external_driver_id == payload.external_driver_id).one_or_none()
    if mapping and mapping.driver_id:
        loc = db.query(DriverLocation).filter(DriverLocation.driver_id == mapping.driver_id).one_or_none()
        if loc is None:
            db.add(DriverLocation(driver_id=mapping.driver_id, lat=payload.lat, lon=payload.lon))
        else:
            loc.lat = payload.lat
            loc.lon = payload.lon
            loc.updated_at = datetime.now(timezone.utc)
        db.flush()
        return {"detail": "ok"}
    # no mapping — accept but do nothing
    return {"detail": "ignored"}
