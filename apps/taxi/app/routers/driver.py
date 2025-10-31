from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..auth import get_current_user, get_db
from ..models import User, Driver, DriverLocation, Ride, RideRating, TaxiWallet
from ..ws_manager import ride_ws_manager
from ..schemas import DriverApplyIn, DriverStatusIn, DriverLocationIn, UserOut, DriverRatingsOut, DriverProfileOut
from ..utils_fraud import is_suspended_driver
from ..config import settings


router = APIRouter(prefix="/driver", tags=["driver"])


def require_driver(user: User):
    if user.role != "driver":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver only")


@router.post("/apply")
def apply_driver(payload: DriverApplyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # DEV: promote to driver and create driver record
    if user.role != "driver":
        user.role = "driver"
        db.flush()
    drv = db.query(Driver).filter(Driver.user_id == user.id).one_or_none()
    if drv is None:
        drv = Driver(user_id=user.id, vehicle_make=payload.vehicle_make, vehicle_plate=payload.vehicle_plate, status="offline")
        db.add(drv)
        db.flush()
        # Ensure Taxi Wallet exists for driver
        w = db.query(TaxiWallet).filter(TaxiWallet.driver_id == drv.id).one_or_none()
        if w is None:
            db.add(TaxiWallet(driver_id=drv.id, balance_cents=0))
            db.flush()
    return {"detail": "driver enabled"}


@router.put("/status")
def update_status(payload: DriverStatusIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_driver(user)
    drv = db.query(Driver).filter(Driver.user_id == user.id).one()
    if is_suspended_driver(db, str(drv.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="driver_suspended")
    if payload.status not in ("offline", "available", "busy"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
    drv.status = payload.status
    db.flush()
    return {"detail": "ok", "status": drv.status}


@router.put("/location")
def update_location(payload: DriverLocationIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_driver(user)
    drv = db.query(Driver).filter(Driver.user_id == user.id).one()
    if is_suspended_driver(db, str(drv.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="driver_suspended")
    loc = db.query(DriverLocation).filter(DriverLocation.driver_id == drv.id).one_or_none()
    if loc is None:
        loc = DriverLocation(driver_id=drv.id, lat=payload.lat, lon=payload.lon, updated_at=datetime.now(timezone.utc))
        db.add(loc)
    else:
        loc.lat = payload.lat
        loc.lon = payload.lon
        loc.updated_at = datetime.now(timezone.utc)
    db.flush()
    # Broadcast to rider if driver has an active ride (assigned/accepted/enroute)
    active = (
        db.query(Ride)
        .filter(Ride.driver_id == drv.id)
        .filter(Ride.status.in_(["assigned", "accepted", "enroute"]))
        .order_by(Ride.created_at.desc())
        .first()
    )
    if active is not None:
        try:
            import datetime as _dt
            payload_ws = {
                "type": "driver_location",
                "ride_id": str(active.id),
                "lat": payload.lat,
                "lon": payload.lon,
                "ts": _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            # fire and forget
            import anyio
            anyio.from_thread.run(ride_ws_manager.broadcast_ride_status, str(active.id), payload_ws)
        except Exception:
            pass
    # Optional MQTT publish for realtime streams
    try:
        if settings.MQTT_BROKER_HOST:
            import json
            from paho.mqtt import publish as _pub
            topic_pref = (settings.MQTT_TOPIC_PREFIX or "taxi").strip("/")
            # Publish per-driver and per-ride topics
            base_payload = {
                "driver_id": str(drv.id),
                "lat": payload.lat,
                "lon": payload.lon,
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            msgs = [(f"{topic_pref}/driver/{drv.id}/location", json.dumps(base_payload), 0, False)]
            if active is not None:
                ride_msg = base_payload | {"ride_id": str(active.id)}
                msgs.append((f"{topic_pref}/ride/{active.id}/driver_location", json.dumps(ride_msg), 0, False))
            _pub.multiple(
                msgs,
                hostname=settings.MQTT_BROKER_HOST,
                port=int(getattr(settings, "MQTT_BROKER_PORT", 1883)),
                client_id="taxi-api",
                keepalive=10,
            )
    except Exception:
        pass
    return {"detail": "ok"}


@router.get("/ratings", response_model=DriverRatingsOut)
def get_ratings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_driver(user)
    drv = db.query(Driver).filter(Driver.user_id == user.id).one()
    avg_, cnt = db.query(func.avg(RideRating.rating), func.count(RideRating.id)).filter(RideRating.driver_id == drv.id).one()
    avg = float(avg_) if avg_ is not None else None
    return DriverRatingsOut(avg_rating=avg, ratings_count=int(cnt or 0))


@router.get("/profile", response_model=DriverProfileOut)
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_driver(user)
    drv = db.query(Driver).filter(Driver.user_id == user.id).one()
    avg_, cnt = db.query(func.avg(RideRating.rating), func.count(RideRating.id)).filter(RideRating.driver_id == drv.id).one()
    avg = float(avg_) if avg_ is not None else None
    return DriverProfileOut(
        id=str(user.id),
        phone=user.phone,
        name=user.name,
        status=drv.status,
        vehicle_make=drv.vehicle_make,
        vehicle_plate=drv.vehicle_plate,
        avg_rating=avg,
        ratings_count=int(cnt or 0),
    )


@router.get("/earnings")
def get_earnings(days: int = 7, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_driver(user)
    from datetime import datetime, timedelta, timezone
    if days <= 0:
        days = 7
    since = datetime.now(timezone.utc) - timedelta(days=days)
    drv = db.query(Driver).filter(Driver.user_id == user.id).one()
    q = db.query(func.coalesce(func.sum(Ride.final_fare_cents), 0)).filter(Ride.driver_id == drv.id).filter(Ride.status == "completed").filter(Ride.completed_at != None).filter(Ride.completed_at >= since)  # noqa: E711
    total_cents = int(q.scalar() or 0)
    return {"days": days, "total_earnings_cents": total_cents}
