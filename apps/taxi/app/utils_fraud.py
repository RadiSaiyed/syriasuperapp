from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from .models import FraudEvent, Driver, DriverLocation, Ride, Suspension
from .utils import haversine_km
from .config import settings


def record_fraud_event(db: Session, *, user_id: Optional[str] = None, driver_id: Optional[str] = None, type: str, data: Optional[dict] = None) -> None:
    try:
        ev = FraudEvent(user_id=user_id, driver_id=driver_id, type=type, data=data or {})
        db.add(ev)
        db.flush()
    except Exception:
        try:
            db.rollback(); db.commit()
        except Exception:
            pass


def enforce_rider_velocity(db: Session, user_id: str) -> None:
    try:
        window_secs = max(10, int(getattr(settings, "FRAUD_RIDER_WINDOW_SECS", 60)))
        max_reqs = max(1, int(getattr(settings, "FRAUD_RIDER_MAX_REQUESTS", 6)))
    except Exception:
        window_secs, max_reqs = 60, 6
    if max_reqs <= 0:
        return
    since = datetime.utcnow() - timedelta(seconds=window_secs)
    cnt = db.query(Ride).filter(Ride.rider_user_id == user_id).filter(Ride.created_at >= since).count()
    if cnt >= max_reqs:
        record_fraud_event(db, user_id=user_id, type="rider.velocity_block", data={"count": cnt, "window_secs": window_secs})
        # Optional auto-suspension
        if getattr(settings, "FRAUD_AUTOSUSPEND_ON_VELOCITY", False):
            until = datetime.utcnow() + timedelta(minutes=max(1, int(getattr(settings, "FRAUD_AUTOSUSPEND_MINUTES", 10))))
            susp = Suspension(user_id=user_id, reason="velocity", until=until, active=True)
            db.add(susp); db.flush()
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many ride requests")


def _get_driver_location(db: Session, driver_id: str) -> Optional[DriverLocation]:
    return db.query(DriverLocation).filter(DriverLocation.driver_id == driver_id).one_or_none()


def require_driver_location_fresh_and_near(db: Session, driver: Driver, *, target_lat: float, target_lon: float, max_age_secs: int, max_dist_km: float, stage: str) -> None:
    loc = _get_driver_location(db, driver.id)
    if loc is None:
        record_fraud_event(db, driver_id=str(driver.id), type=f"driver.loc_missing.{stage}")
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="driver_location_missing")
    # Freshness
    age = (datetime.utcnow() - loc.updated_at).total_seconds()
    if age > max_age_secs:
        record_fraud_event(db, driver_id=str(driver.id), type=f"driver.loc_stale.{stage}", data={"age_secs": age})
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="driver_location_stale")
    # Proximity
    dist = haversine_km(loc.lat, loc.lon, target_lat, target_lon)
    if dist > max_dist_km:
        record_fraud_event(db, driver_id=str(driver.id), type=f"driver.loc_far.{stage}", data={"dist_km": dist})
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="driver_too_far")


def is_suspended_user(db: Session, user_id: str) -> bool:
    from datetime import datetime
    now = datetime.utcnow()
    q = db.query(Suspension).filter(Suspension.user_id == user_id, Suspension.active == True)  # noqa: E712
    rows = [s for s in q.all() if (s.until is None or s.until >= now)]
    return len(rows) > 0


def is_suspended_driver(db: Session, driver_id: str) -> bool:
    from datetime import datetime
    now = datetime.utcnow()
    q = db.query(Suspension).filter(Suspension.driver_id == driver_id, Suspension.active == True)  # noqa: E712
    rows = [s for s in q.all() if (s.until is None or s.until >= now)]
    return len(rows) > 0
