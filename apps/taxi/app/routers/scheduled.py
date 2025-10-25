from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..config import settings
from ..models import (
    User,
    ScheduledRide,
    ScheduledRideStop,
    Ride,
    Driver,
    DriverLocation,
    PromoCode,
    PromoRedemption,
    RideStop,
)
from ..schemas import (
    ScheduleRideIn,
    ScheduleRideOut,
    ScheduledRideItemOut,
    ScheduledRidesListOut,
    StopIn,
)
from .rides import (
    _surge_multiplier_for_location,
    _quote_fare_cents,
    _apply_promo_quote,
    _find_nearest_available_driver,
)


router = APIRouter(prefix="/rides", tags=["rides"])


@router.post("/schedule", response_model=ScheduleRideOut)
def schedule_ride(payload: ScheduleRideIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Block suspended riders
    from ..utils_fraud import is_suspended_user
    if is_suspended_user(db, str(user.id)):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_suspended")
    # Normalize input to aware UTC and compare properly (avoid naive/aware mismatch)
    sf = payload.scheduled_for
    if sf.tzinfo is None:
        sf_utc = sf.replace(tzinfo=timezone.utc)
    else:
        sf_utc = sf.astimezone(timezone.utc)
    now_utc = datetime.now(timezone.utc)
    if sf_utc <= now_utc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scheduled_for must be in the future")
    surge = _surge_multiplier_for_location(db, payload.pickup_lat, payload.pickup_lon)
    stops = [s.dict() for s in (payload.stops or [])]
    fare_cents, dist_km, _ = _quote_fare_cents(
        payload.pickup_lat,
        payload.pickup_lon,
        payload.dropoff_lat,
        payload.dropoff_lon,
        surge,
        stops,
    )
    applied_code = None
    discount_cents = 0
    if payload.promo_code:
        applied_code, discount_cents = _apply_promo_quote(db, payload.promo_code, fare_cents)
    final_quote = max(0, fare_cents - discount_cents)
    # Persist as naive UTC in DB for consistency with other timestamps
    sched = ScheduledRide(
        rider_user_id=user.id,
        pickup_lat=payload.pickup_lat,
        pickup_lon=payload.pickup_lon,
        dropoff_lat=payload.dropoff_lat,
        dropoff_lon=payload.dropoff_lon,
        scheduled_for=sf_utc.replace(tzinfo=None),
        promo_code=applied_code,
    )
    db.add(sched)
    db.flush()
    for i, s in enumerate(stops):
        db.add(ScheduledRideStop(scheduled_ride_id=sched.id, seq=i, lat=s["lat"], lon=s["lon"]))
    return ScheduleRideOut(
        id=str(sched.id),
        scheduled_for=sched.scheduled_for,
        quoted_fare_cents=fare_cents,
        final_quote_cents=final_quote,
        distance_km=dist_km,
        surge_multiplier=surge,
        applied_promo_code=applied_code,
        discount_cents=discount_cents,
    )


@router.post("/dispatch_scheduled")
def dispatch_scheduled(window_minutes: int = 10, db: Session = Depends(get_db)):
    # DEV helper: materialize scheduled rides due within the next window
    if settings.ENV != "dev":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    if window_minutes <= 0:
        window_minutes = 10
    now = datetime.utcnow()
    cutoff = now + timedelta(minutes=window_minutes)
    due = db.query(ScheduledRide).filter(ScheduledRide.scheduled_for <= cutoff).all()
    dispatched = 0
    for s in due:
        # Create a live ride if not already dispatched (no redemption with this sched id marker)
        # Find nearest driver and compute fare based on current surge
        surge = _surge_multiplier_for_location(db, s.pickup_lat, s.pickup_lon)
        sched_stops = db.query(ScheduledRideStop).filter(ScheduledRideStop.scheduled_ride_id == s.id).order_by(ScheduledRideStop.seq.asc()).all()
        stops = [{"lat": r.lat, "lon": r.lon} for r in sched_stops]
        fare_cents, dist_km, _ = _quote_fare_cents(s.pickup_lat, s.pickup_lon, s.dropoff_lat, s.dropoff_lon, surge, stops)
        applied_code = None
        discount_cents = 0
        if s.promo_code:
            applied_code, discount_cents = _apply_promo_quote(db, s.promo_code, fare_cents, str(s.rider_user_id))
            fare_cents = max(0, fare_cents - discount_cents)
        nearest = _find_nearest_available_driver(db, s.pickup_lat, s.pickup_lon)
        ride = Ride(
            rider_user_id=s.rider_user_id,
            driver_id=nearest.id if nearest else None,
            status="assigned" if nearest else "requested",
            pickup_lat=s.pickup_lat,
            pickup_lon=s.pickup_lon,
            dropoff_lat=s.dropoff_lat,
            dropoff_lon=s.dropoff_lon,
            quoted_fare_cents=fare_cents,
            distance_km=dist_km,
        )
        db.add(ride)
        db.flush()  # ensure ride.id is available for downstream inserts
        if stops:
            for i, st in enumerate(stops):
                db.add(RideStop(ride_id=ride.id, seq=i, lat=st["lat"], lon=st["lon"]))
        if nearest:
            nearest.status = "busy"
        if applied_code and discount_cents:
            promo = db.query(PromoCode).filter(PromoCode.code == applied_code).one_or_none()
            if promo:
                promo.uses_count = (promo.uses_count or 0) + 1
                db.add(PromoRedemption(promo_code_id=promo.id, ride_id=ride.id, rider_user_id=s.rider_user_id))
        # Delete or keep scheduled record? We'll delete after dispatch
        db.delete(s)
        dispatched += 1
    return {"dispatched": dispatched, "window_minutes": window_minutes}


@router.get("/scheduled", response_model=ScheduledRidesListOut)
def list_scheduled(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(ScheduledRide)
        .filter(ScheduledRide.rider_user_id == user.id)
        .order_by(ScheduledRide.scheduled_for.asc())
        .all()
    )
    items = []
    for s in rows:
        stops = (
            db.query(ScheduledRideStop)
            .filter(ScheduledRideStop.scheduled_ride_id == s.id)
            .order_by(ScheduledRideStop.seq.asc())
            .all()
        )
        items.append(
            ScheduledRideItemOut(
                id=str(s.id),
                scheduled_for=s.scheduled_for,
                pickup_lat=s.pickup_lat,
                pickup_lon=s.pickup_lon,
                dropoff_lat=s.dropoff_lat,
                dropoff_lon=s.dropoff_lon,
                applied_promo_code=s.promo_code,
                stops=[StopIn(lat=r.lat, lon=r.lon) for r in stops] or None,
            )
        )
    return ScheduledRidesListOut(scheduled=items)


@router.delete("/scheduled/{scheduled_id}")
def cancel_scheduled(scheduled_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Find scheduled ride belonging to user
    s = db.query(ScheduledRide).filter(ScheduledRide.id == scheduled_id, ScheduledRide.rider_user_id == user.id).one_or_none()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    # Delete child stops first (no cascade configured)
    db.query(ScheduledRideStop).filter(ScheduledRideStop.scheduled_ride_id == s.id).delete()
    db.delete(s)
    return {"status": "canceled", "id": str(scheduled_id)}
