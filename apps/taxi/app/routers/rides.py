from datetime import datetime, timezone
import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request, Header
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from ..auth import get_current_user, get_db
from ..config import settings
from datetime import datetime, timedelta
from ..models import User, Driver, DriverLocation, Ride, RideRating, RideStop, PromoCode, PromoRedemption, TaxiWallet, TaxiWalletEntry
from ..schemas import RideRequestIn, RideOut, RidesListOut, RideQuoteOut, RideRatingIn, CancelIn, RideReceiptOut
import httpx
from ..ws_manager import ride_ws_manager, driver_ws_manager
from ..utils import haversine_km
from ..maps import get_maps_provider
from ..utils_fraud import enforce_rider_velocity, require_driver_location_fresh_and_near, is_suspended_user, is_suspended_driver, record_fraud_event
from ..push import send_push_to_user
from ..payments_cb import allowed as pay_allowed, record as pay_record
from prometheus_client import Counter, Histogram
import os


router = APIRouter(prefix="/rides", tags=["rides"])

# Metrics
MATCH_ATTEMPTS = Counter(
    "taxi_matching_attempts_total",
    "Driver matching attempts",
    ["result"],
)
REASSIGN_EVENTS = Counter(
    "taxi_reassign_events_total",
    "Reassignment events",
    ["reason", "result"],
)
STATUS_TRANSITIONS = Counter(
    "taxi_ride_status_transitions_total",
    "Ride status transitions",
    ["from", "to"],
)
TIMEOUT_REAPED = Counter(
    "taxi_timeouts_reassigned_total",
    "Assigned rides reaped due to timeout",
    ["stage", "result"],
)
ETA_ABS_ERR_MIN = Histogram(
    "taxi_eta_pickup_abs_error_minutes",
    "Absolute error between predicted and actual pickup ETA (minutes)",
    buckets=(0.5, 1, 2, 3, 5, 8, 13, 21, 34),
)


def _count_transition(frm: str | None, to: str | None):
    try:
        STATUS_TRANSITIONS.labels(str(frm or ""), str(to or "")).inc()
    except Exception:
        pass


def _driver_has_min_balance(db: Session, driver: Driver, min_cents: int) -> bool:
    if min_cents <= 0:
        return True
    # Prefer Taxi Wallet if enabled
    if getattr(settings, "TAXI_WALLET_ENABLED", True):
        w = db.query(TaxiWallet).filter(TaxiWallet.driver_id == driver.id).one_or_none()
        bal = int(w.balance_cents) if w else 0
        return bal >= min_cents
    # Fallback to Payments wallet balance
    try:
        user = db.get(User, driver.user_id)
        if not user:
            return False
        phone = user.phone
        now = datetime.now(timezone.utc)
        ttl = max(1, int(getattr(settings, "PAYMENTS_WALLET_CACHE_SECS", 30)))
        global _WALLET_BAL_CACHE  # type: ignore
        if "_WALLET_BAL_CACHE" not in globals():
            _WALLET_BAL_CACHE = {}
        bal_cache = _WALLET_BAL_CACHE  # type: ignore
        cached = bal_cache.get(phone)
        if cached:
            bal, ts = cached
            if isinstance(ts, datetime) and (now - ts) <= timedelta(seconds=ttl):
                return int(bal) >= min_cents
        import httpx
        from superapp_shared.internal_hmac import sign_internal_request_headers
        headers = sign_internal_request_headers({"phone": phone}, settings.PAYMENTS_INTERNAL_SECRET)
        with httpx.Client(timeout=3.0) as client:
            r = client.get(
                f"{settings.PAYMENTS_BASE_URL}/internal/wallet",
                params={"phone": phone},
                headers=headers,
            )
            if r.status_code >= 400:
                return False
            bal = (r.json() or {}).get("balance_cents")
            if not isinstance(bal, int):
                return False
            bal_cache[phone] = (int(bal), now)
            return int(bal) >= min_cents
    except Exception:
        return False

def _route_distance_duration(pickup_lat: float, pickup_lon: float, stops: list[dict] | None, dropoff_lat: float, dropoff_lon: float) -> tuple[float, int]:
    pts: list[tuple[float, float]] = [(pickup_lat, pickup_lon)]
    for s in (stops or []):
        pts.append((s["lat"], s["lon"]))
    pts.append((dropoff_lat, dropoff_lon))
    prov = get_maps_provider()
    dist_km, mins = prov.route_distance_duration(pts)
    return dist_km, mins


def _route_info(pickup_lat: float, pickup_lon: float, stops: list[dict] | None, dropoff_lat: float, dropoff_lon: float) -> tuple[float, int, str | None]:
    pts: list[tuple[float, float]] = [(pickup_lat, pickup_lon)]
    for s in (stops or []):
        pts.append((s["lat"], s["lon"]))
    pts.append((dropoff_lat, dropoff_lon))
    prov = get_maps_provider()
    from ..config import settings as _cfg
    want_poly = getattr(_cfg, "MAPS_INCLUDE_POLYLINE", False)
    d_km, mins, poly = prov.route(pts, want_polyline=want_poly)
    return d_km, mins, poly


def _quote_fare_cents(pickup_lat: float, pickup_lon: float, dropoff_lat: float, dropoff_lon: float, surge_multiplier: float = 1.0, stops: list[dict] | None = None, ride_class: str | None = None) -> tuple[int, float, int]:
    dist, eta_mins = _route_distance_duration(pickup_lat, pickup_lon, stops, dropoff_lat, dropoff_lon)
    fare_base = settings.BASE_FARE_CENTS + int(round(settings.PER_KM_CENTS * dist))
    fare = int(round(fare_base * max(1.0, surge_multiplier)))
    # Traffic surcharge (ETA slower than baseline pace)
    try:
        base_pace = max(0.1, float(settings.TRAFFIC_BASE_PACE_MIN_PER_KM))
    except Exception:
        base_pace = 2.0
    try:
        surcharge_rate = int(settings.TRAFFIC_SURCHARGE_PER_MIN_CENTS)
    except Exception:
        surcharge_rate = 0
    traffic_extra = 0
    if surcharge_rate > 0 and eta_mins > 0 and dist > 0:
        baseline_eta = base_pace * dist
        slow_minutes = max(0.0, eta_mins - baseline_eta)
        if slow_minutes > 0:
            traffic_extra = int(round(slow_minutes * surcharge_rate))
            try:
                max_mult = float(settings.TRAFFIC_SURCHARGE_MAX_MULTIPLIER)
            except Exception:
                max_mult = 3.0
            if max_mult > 0:
                fare_cap = int(round(fare_base * max_mult))
                fare = min(fare + traffic_extra, max(fare, fare_cap))
            else:
                fare += traffic_extra
    else:
        traffic_extra = 0
    # Apply ride class multiplier if provided
    try:
        if ride_class:
            mult = float(settings.RIDE_CLASS_MULTIPLIERS.get(ride_class.strip().lower(), 1.0))
            if mult > 0:
                fare = int(round(fare * mult))
    except Exception:
        pass
    # Apply per-class minimum fare and global base floor
    try:
        cls = (ride_class or '').strip().lower()
        min_by_class = int(settings.RIDE_CLASS_MIN_FARE_CENTS.get(cls, 0)) if cls else 0
    except Exception:
        min_by_class = 0
    fare = max(fare, settings.BASE_FARE_CENTS, int(min_by_class or 0))
    return fare, dist, int(round(eta_mins))


def _find_nearest_available_driver(
    db: Session,
    pickup_lat: float,
    pickup_lon: float,
    required_fee_cents: int | None = None,
    relax_min_balance: bool = False,
    radius_km: float | None = None,
    ride_class: str | None = None,
):
    avail = (
        db.query(Driver, DriverLocation)
        .join(DriverLocation, Driver.id == DriverLocation.driver_id)
        .filter(Driver.status == "available")
        .all()
    )
    def _has_min_balance(driver: Driver) -> bool:
        if relax_min_balance:
            return True
        if not required_fee_cents or required_fee_cents <= 0:
            return True
        # Be safe: failures => False
        return _driver_has_min_balance(db, driver, required_fee_cents)

    want_class = (ride_class or "").strip().lower() or None
    eff_radius = float(radius_km or settings.ASSIGN_RADIUS_KM)
    candidates: list[tuple[Driver, float]] = []
    for drv, loc in avail:
        # Filter by class if requested
        if want_class:
            try:
                drv_class = (getattr(drv, 'ride_class', None) or '').strip().lower() or None
            except Exception:
                drv_class = None
            if drv_class != want_class:
                continue
        d = haversine_km(pickup_lat, pickup_lon, loc.lat, loc.lon)
        if d > eff_radius:
            continue
        if not _has_min_balance(drv):
            continue
        candidates.append((drv, d))
    candidates.sort(key=lambda item: item[1])

    for drv, _dist in candidates:
        locked = (
            db.execute(
                select(Driver)
                .where(Driver.id == drv.id, Driver.status == "available")
                .with_for_update(skip_locked=True)
            ).scalar_one_or_none()
        )
        if not locked:
            continue
        return locked
    return None


def _available_drivers_within_radius(db: Session, pickup_lat: float, pickup_lon: float) -> int:
    avail = (
        db.query(Driver, DriverLocation)
        .join(DriverLocation, Driver.id == DriverLocation.driver_id)
        .filter(Driver.status == "available")
        .all()
    )
    count = 0
    for drv, loc in avail:
        d = haversine_km(pickup_lat, pickup_lon, loc.lat, loc.lon)
        if d <= settings.ASSIGN_RADIUS_KM:
            count += 1
    return count


def _surge_multiplier_for_location(db: Session, pickup_lat: float, pickup_lon: float) -> float:
    try:
        threshold = max(0, int(settings.SURGE_AVAILABLE_THRESHOLD))
        step = max(0.0, float(settings.SURGE_STEP_PER_MISSING))
        max_mult = max(1.0, float(settings.SURGE_MAX_MULTIPLIER))
    except Exception:
        threshold, step, max_mult = 3, 0.25, 2.0
    available = _available_drivers_within_radius(db, pickup_lat, pickup_lon)
    if available >= threshold:
        return 1.0
    missing = threshold - available
    mult = 1.0 + missing * step
    if mult > max_mult:
        mult = max_mult
    return mult


def _eta_minutes_from_provider(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> int:
    prov = get_maps_provider()
    return prov.eta_minutes(from_lat, from_lon, to_lat, to_lon)


@router.post("/quote", response_model=RideQuoteOut)
def quote_ride(payload: RideRequestIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    surge = _surge_multiplier_for_location(db, payload.pickup_lat, payload.pickup_lon)
    stops = [s.dict() for s in (payload.stops or [])]
    fare_cents, dist_km, eta_traffic = _quote_fare_cents(
        payload.pickup_lat,
        payload.pickup_lon,
        payload.dropoff_lat,
        payload.dropoff_lon,
        surge,
        stops,
        getattr(payload, 'ride_class', None),
    )
    # Optional polyline for UI if enabled
    _, _, poly = _route_info(payload.pickup_lat, payload.pickup_lon, stops, payload.dropoff_lat, payload.dropoff_lon)
    applied_code = None
    discount_cents = 0
    if getattr(payload, "promo_code", None):
        applied_code, discount_cents = _apply_promo_quote(db, payload.promo_code, fare_cents, str(user.id))
    final_quote = max(0, fare_cents - discount_cents)
    # Estimate driver ETA to pickup using nearest available driver (if any)
    eta_pickup = None
    try:
        nearest_drv = _find_nearest_available_driver(db, payload.pickup_lat, payload.pickup_lon, None)
        if nearest_drv:
            loc = db.query(DriverLocation).filter(DriverLocation.driver_id == nearest_drv.id).one_or_none()
            if loc:
                eta_pickup = _eta_minutes_from_provider(loc.lat, loc.lon, payload.pickup_lat, payload.pickup_lon)
    except Exception:
        eta_pickup = None
    return RideQuoteOut(
        quoted_fare_cents=fare_cents,
        final_quote_cents=final_quote,
        distance_km=dist_km,
        surge_multiplier=surge,
        eta_to_pickup_minutes=eta_pickup,
        applied_promo_code=applied_code,
        discount_cents=discount_cents,
        route_polyline=poly,
        ride_class=getattr(payload, 'ride_class', None),
        eta_minutes=eta_traffic,
    )


def _assign_driver(db: Session, ride: Ride, driver: Driver | None):
    if driver is None:
        # no assignment
        try:
            MATCH_ATTEMPTS.labels("none").inc()
        except Exception:
            pass
        return False
    prev = ride.status
    ride.driver_id = driver.id
    ride.status = "assigned"
    driver.status = "busy"
    db.flush()
    try:
        MATCH_ATTEMPTS.labels("assigned").inc()
    except Exception:
        pass
    _count_transition(prev, ride.status)
    # Notify driver channel about assignment
    try:
        import anyio
        anyio.from_thread.run(driver_ws_manager.broadcast_to_driver, str(driver.id), {"type": "driver_assignment", "ride_id": str(ride.id), "status": ride.status})
    except Exception:
        pass
    # Push notify driver (best effort) — include data payload for in-app handling
    try:
        send_push_to_user(
            db,
            str(driver.user_id),
            "New ride assigned",
            f"Pickup nearby — ride {ride.id}",
            app_mode="driver",
            data={"type": "driver_assignment", "ride_id": str(ride.id)},
            content_available=True,
        )
    except Exception:
        pass
    return True


@router.post("/request", response_model=RideOut)
def request_ride(payload: RideRequestIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ("rider", "driver"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user role")
    # Suspensions
    if is_suspended_user(db, str(user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_suspended")
    # Fraud: rider velocity
    try:
        enforce_rider_velocity(db, str(user.id))
    except HTTPException:
        raise
    surge = _surge_multiplier_for_location(db, payload.pickup_lat, payload.pickup_lon)
    stops = [s.dict() for s in (payload.stops or [])]
    fare_cents, dist_km, _eta_total = _quote_fare_cents(payload.pickup_lat, payload.pickup_lon, payload.dropoff_lat, payload.dropoff_lon, surge, stops, getattr(payload, 'ride_class', None))
    applied_code = None
    discount_cents = 0
    if getattr(payload, "promo_code", None):
        applied_code, discount_cents = _apply_promo_quote(db, payload.promo_code, fare_cents, str(user.id))
        fare_cents = max(0, fare_cents - discount_cents)

    # Find nearest available driver within radius
    # Required platform fee based on quoted fare (cash flow)
    fee_bps = settings.PLATFORM_FEE_BPS
    required_fee = int((fare_cents * fee_bps + 5000) // 10000) if fee_bps and fare_cents else 0
    # Per-class required driver balance floor
    try:
        cls_min_bal = int(settings.RIDE_CLASS_MIN_DRIVER_BALANCE_CENTS.get((getattr(payload, 'ride_class', None) or '').strip().lower(), 0))
    except Exception:
        cls_min_bal = 0
    min_required = max(int(required_fee or 0), int(cls_min_bal or 0))
    nearest = _find_nearest_available_driver(db, payload.pickup_lat, payload.pickup_lon, min_required, ride_class=getattr(payload, 'ride_class', None))

    # Determine beneficiary & pay mode
    for_name = (getattr(payload, 'for_name', None) or None)
    for_phone = (getattr(payload, 'for_phone', None) or None)
    pay_mode = (getattr(payload, 'pay_mode', None) or None)
    if pay_mode not in (None, 'self', 'cash'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_pay_mode")

    ride = Ride(
        rider_user_id=user.id,
        driver_id=nearest.id if nearest else None,
        status="assigned" if nearest else "requested",
        pickup_lat=payload.pickup_lat,
        pickup_lon=payload.pickup_lon,
        dropoff_lat=payload.dropoff_lat,
        dropoff_lon=payload.dropoff_lon,
        quoted_fare_cents=fare_cents,
        distance_km=dist_km,
        passenger_name=for_name,
        passenger_phone=for_phone,
        payer_mode=pay_mode,
        ride_class=(getattr(payload, 'ride_class', None) or None),
    )
    db.add(ride)
    # Persist stops if provided
    if stops:
        for i, s in enumerate(stops):
            db.add(RideStop(ride_id=ride.id, seq=i, lat=s["lat"], lon=s["lon"]))
    eta_to_pickup = None
    if nearest:
        nearest.status = "busy"
        loc = db.query(DriverLocation).filter(DriverLocation.driver_id == nearest.id).one_or_none()
        if loc:
            eta_to_pickup = _eta_minutes_from_provider(loc.lat, loc.lon, payload.pickup_lat, payload.pickup_lon)
    # Record promo redemption after ride persisted
    if applied_code and discount_cents:
        promo = db.query(PromoCode).filter(PromoCode.code == applied_code).one_or_none()
        if promo:
            promo.uses_count = (promo.uses_count or 0) + 1
            db.add(PromoRedemption(promo_code_id=promo.id, ride_id=ride.id, rider_user_id=user.id))
    db.flush()

    # Optional: Prepay fare into escrow wallet (rider -> TAXI_ESCROW_WALLET_PHONE)
    try:
        # Effective prepay: explicit payload.prepay OR pay_mode=='self' when prepay unspecified
        _prepay_raw = getattr(payload, 'prepay', None)
        _prepay_effective = (bool(_prepay_raw) if _prepay_raw is not None else (pay_mode == 'self'))
        if _prepay_effective and getattr(settings, "TAXI_ESCROW_WALLET_PHONE", None) and settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and pay_allowed("escrow_transfer"):
            escrow_phone = settings.TAXI_ESCROW_WALLET_PHONE
            # Skip if zero fare
            amt = int(fare_cents or 0)
            if amt > 0 and escrow_phone:
                body = {"from_phone": user.phone, "to_phone": escrow_phone, "amount_cents": amt}
                from superapp_shared.internal_hmac import sign_internal_request_headers
                headers = sign_internal_request_headers(body, settings.PAYMENTS_INTERNAL_SECRET, request.headers.get("X-Request-ID", ""))
                headers["X-Idempotency-Key"] = f"taxi:{ride.id}:escrow"
                import httpx as _httpx
                with _httpx.Client(timeout=5.0) as client:
                    r = client.post(f"{settings.PAYMENTS_BASE_URL}/internal/transfer", json=body, headers=headers)
                    pay_record("escrow_transfer", r.status_code < 400)
                    if r.status_code >= 400:
                        # Bubble up as a clear error so client can show wallet insufficient
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "insufficient_rider_balance", "message": (r.json().get('detail') if r.headers.get('content-type','').startswith('application/json') else r.text)})
                    # Mark escrow on ride
                    ride.escrow_amount_cents = amt
    except HTTPException:
        raise
    except Exception:
        # Non-fatal: if escrow fails due to network or other, return 502 so client can retry or fallback
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="escrow_error")
    return RideOut(
        id=str(ride.id),
        status=ride.status,
        rider_user_id=str(ride.rider_user_id),
        driver_id=str(ride.driver_id) if ride.driver_id else None,
        quoted_fare_cents=ride.quoted_fare_cents,
        final_fare_cents=ride.final_fare_cents,
        distance_km=ride.distance_km,
        surge_multiplier=surge,
        eta_to_pickup_minutes=eta_to_pickup,
        stops=payload.stops or None,
        applied_promo_code=applied_code,
        discount_cents=discount_cents,
        route_polyline=_route_info(payload.pickup_lat, payload.pickup_lon, stops, payload.dropoff_lat, payload.dropoff_lon)[2],
        for_name=for_name,
        for_phone=for_phone,
        pay_mode=pay_mode,
        pickup_lat=ride.pickup_lat,
        pickup_lon=ride.pickup_lon,
        dropoff_lat=ride.dropoff_lat,
        dropoff_lon=ride.dropoff_lon,
        created_at=ride.created_at,
        started_at=ride.started_at,
        completed_at=ride.completed_at,
        rider_reward_applied=ride.rider_reward_applied,
        driver_reward_fee_waived=ride.driver_reward_fee_waived,
    )


def _apply_promo_quote(db: Session, code: str, fare_cents: int, rider_user_id: str | None = None) -> tuple[str | None, int]:
    pc = db.query(PromoCode).filter(PromoCode.code == code).one_or_none()
    if pc is None or not pc.active:
        return None, 0
    from datetime import datetime as _dt
    now = _dt.utcnow()
    if pc.valid_from and now < pc.valid_from:
        return None, 0
    if pc.valid_until and now > pc.valid_until:
        return None, 0
    if pc.max_uses is not None and pc.uses_count >= pc.max_uses:
        return None, 0
    if rider_user_id and getattr(pc, 'per_user_max_uses', None):
        if pc.per_user_max_uses is not None and pc.per_user_max_uses > 0:
            cnt = db.query(func.count(PromoRedemption.id)).filter(PromoRedemption.promo_code_id == pc.id, PromoRedemption.rider_user_id == rider_user_id).scalar() or 0
            if cnt >= pc.per_user_max_uses:
                return None, 0
    if pc.min_fare_cents is not None and fare_cents < pc.min_fare_cents:
        return None, 0
    discount = 0
    if pc.percent_off_bps:
        discount = max(discount, int((fare_cents * pc.percent_off_bps + 5000) // 10000))
    if pc.amount_off_cents:
        discount = max(discount, int(pc.amount_off_cents))
    discount = min(discount, fare_cents)
    return pc.code, discount


def _get_driver_for_user(db: Session, user: User) -> Driver:
    drv = db.query(Driver).filter(Driver.user_id == user.id).one_or_none()
    if drv is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver not found")
    return drv


def _get_ride(db: Session, ride_id: str) -> Ride:
    ride = db.get(Ride, ride_id)
    if ride is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    return ride


@router.get("/{ride_id}", response_model=RideOut)
def get_ride(ride_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = _get_ride(db, ride_id)
    if user.role == "driver":
        drv = _get_driver_for_user(db, user)
        if r.driver_id != drv.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    else:
        if r.rider_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    stops = db.query(RideStop).filter(RideStop.ride_id == r.id).order_by(RideStop.seq.asc()).all()
    return RideOut(
        id=str(r.id),
        status=r.status,
        rider_user_id=str(r.rider_user_id),
        driver_id=str(r.driver_id) if r.driver_id else None,
        quoted_fare_cents=r.quoted_fare_cents,
        final_fare_cents=r.final_fare_cents,
        distance_km=r.distance_km,
        ride_class=getattr(r, 'ride_class', None),
        stops=[{"lat": s.lat, "lon": s.lon} for s in stops] or None,
        for_name=getattr(r, 'passenger_name', None),
        for_phone=getattr(r, 'passenger_phone', None),
        pay_mode=getattr(r, 'payer_mode', None),
        pickup_lat=r.pickup_lat,
        pickup_lon=r.pickup_lon,
        dropoff_lat=r.dropoff_lat,
        dropoff_lon=r.dropoff_lon,
        created_at=r.created_at,
        started_at=r.started_at,
        completed_at=r.completed_at,
        rider_reward_applied=getattr(r, 'rider_reward_applied', False),
        driver_reward_fee_waived=getattr(r, 'driver_reward_fee_waived', False),
    )


@router.post("/{ride_id}/accept")
def accept_ride(ride_id: str, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    drv = _get_driver_for_user(db, user)
    if is_suspended_driver(db, str(drv.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="driver_suspended")
    # lock ride row
    ride = (
        db.query(Ride)
        .filter(Ride.id == ride_id)
        .with_for_update()
        .one_or_none()
    )
    if ride is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    if ride.driver_id not in (None, drv.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this driver")
    # Enforce class match if ride has a class
    try:
        ride_cls = (getattr(ride, 'ride_class', None) or '').strip().lower()
        drv_cls = (getattr(drv, 'ride_class', None) or '').strip().lower()
        if ride_cls and drv_cls and ride_cls != drv_cls:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="class_mismatch")
    except HTTPException:
        raise
    except Exception:
        pass
    # idempotent if already accepted by this driver
    if ride.status in ("accepted", "enroute", "completed") and ride.driver_id == drv.id:
        return {"detail": ride.status}
    if ride.status not in ("requested", "assigned"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status transition")
    # Check driver balance for expected fee before assignment
    fee_bps = settings.PLATFORM_FEE_BPS
    expected_fee = int(((ride.quoted_fare_cents or 0) * fee_bps + 5000) // 10000) if fee_bps else 0
    if expected_fee > 0 and getattr(settings, "TAXI_WALLET_ENABLED", True):
        w = db.query(TaxiWallet).filter(TaxiWallet.driver_id == drv.id).with_for_update().one_or_none()
        bal = int(w.balance_cents) if w else 0
        if bal < expected_fee:
            shortfall = expected_fee - bal
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "insufficient_taxi_wallet_balance",
                    "required_fee_cents": expected_fee,
                    "wallet_balance_cents": bal,
                    "shortfall_cents": shortfall,
                    "topup_url": "/driver/taxi_wallet/topup",
                },
            )
    # Fraud: ensure driver is reasonably near pickup and location fresh
    try:
        loc_age = getattr(settings, "FRAUD_DRIVER_LOC_MAX_AGE_SECS", 300)
        max_accept_km = getattr(settings, "FRAUD_MAX_ACCEPT_DIST_KM", 3.0)
        require_driver_location_fresh_and_near(db, drv, target_lat=ride.pickup_lat, target_lon=ride.pickup_lon, max_age_secs=int(loc_age), max_dist_km=float(max_accept_km), stage="accept")
    except HTTPException:
        raise
    # Predict ETA to pickup from current driver location
    try:
        loc = db.query(DriverLocation).filter(DriverLocation.driver_id == drv.id).one_or_none()
        if loc:
            pred = _eta_minutes_from_provider(loc.lat, loc.lon, ride.pickup_lat, ride.pickup_lon)
            ride.eta_pickup_predicted_mins = max(0, int(pred))
    except Exception:
        pass
    prev = ride.status
    ride.driver_id = drv.id
    ride.status = "accepted"
    if not getattr(ride, 'accepted_at', None):
        ride.accepted_at = datetime.now(timezone.utc)
    # Driver becomes busy upon accepting
    drv.status = "busy"
    db.flush()
    _count_transition(prev, ride.status)

    # Deduct fee at accept time (idempotent)
    try:
        if expected_fee > 0 and getattr(settings, "TAXI_WALLET_ENABLED", True):
            w = db.query(TaxiWallet).filter(TaxiWallet.driver_id == drv.id).with_for_update().one_or_none()
            if w is None:
                w = TaxiWallet(driver_id=drv.id, balance_cents=0)
                db.add(w)
                db.flush()
            exists = (
                db.query(TaxiWalletEntry)
                .filter(TaxiWalletEntry.wallet_id == w.id, TaxiWalletEntry.ride_id == ride.id, TaxiWalletEntry.type == "fee")
                .one_or_none()
            )
            if exists is None:
                w.balance_cents -= expected_fee
                db.add(
                    TaxiWalletEntry(
                        wallet_id=w.id,
                        type="fee",
                        amount_cents_signed=-expected_fee,
                        ride_id=ride.id,
                        original_fare_cents=ride.quoted_fare_cents,
                        fee_cents=expected_fee,
                        driver_take_home_cents=max(0, (ride.quoted_fare_cents or 0) - expected_fee),
                    )
                )
                # Settle pool -> fee wallet (best effort)
                if settings.TAXI_POOL_WALLET_PHONE and settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and pay_allowed("fee_settle"):
                    fee_payload = {
                        "from_phone": settings.TAXI_POOL_WALLET_PHONE,
                        "to_phone": settings.FEE_WALLET_PHONE,
                        "amount_cents": expected_fee,
                    }
                    from superapp_shared.internal_hmac import sign_internal_request_headers
                    headers2 = sign_internal_request_headers(fee_payload, settings.PAYMENTS_INTERNAL_SECRET, "")
                    headers2["X-Idempotency-Key"] = f"taxi:{ride.id}:fee"
                    import httpx as _httpx
                    try:
                        with _httpx.Client(timeout=5.0) as client:
                            r = client.post(f"{settings.PAYMENTS_BASE_URL}/internal/transfer", headers=headers2, json=fee_payload)
                            pay_record("fee_settle", r.status_code < 400)
                    except Exception:
                        pay_record("fee_settle", False)
                        pass
    except Exception:
        pass
    background_tasks.add_task(
        ride_ws_manager.broadcast_ride_status,
        ride_id,
        {
            "type": "ride_status",
            "ride_id": ride_id,
            "status": ride.status,
            "rider_user_id": str(ride.rider_user_id),
            "driver_id": str(ride.driver_id) if ride.driver_id else None,
            "quoted_fare_cents": ride.quoted_fare_cents,
            "final_fare_cents": ride.final_fare_cents,
            "distance_km": ride.distance_km,
        },
    )
    # Push notify rider on accept
    try:
        send_push_to_user(db, str(ride.rider_user_id), "Ride accepted", "Your driver is on the way", app_mode="rider")
    except Exception:
        pass
    return {"detail": "accepted"}


@router.post("/{ride_id}/start")
def start_ride(ride_id: str, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    drv = _get_driver_for_user(db, user)
    if is_suspended_driver(db, str(drv.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="driver_suspended")
    ride = (
        db.query(Ride)
        .filter(Ride.id == ride_id)
        .with_for_update()
        .one_or_none()
    )
    if ride is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    if ride.driver_id != drv.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your ride")
    if ride.status in ("enroute", "completed"):
        return {"detail": ride.status}
    if ride.status != "accepted":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status transition")
    # Fraud: enforce driver near pickup at start
    try:
        loc_age = getattr(settings, "FRAUD_DRIVER_LOC_MAX_AGE_SECS", 300)
        max_start_km = getattr(settings, "FRAUD_MAX_START_DIST_KM", 0.3)
        require_driver_location_fresh_and_near(db, drv, target_lat=ride.pickup_lat, target_lon=ride.pickup_lon, max_age_secs=int(loc_age), max_dist_km=float(max_start_km), stage="start")
    except HTTPException:
        raise
    prev = ride.status
    ride.status = "enroute"
    ride.started_at = datetime.now(timezone.utc)
    db.flush()
    _count_transition(prev, ride.status)
    # Observe ETA pickup error if we have predicted and accepted_at
    try:
        if ride.accepted_at and getattr(ride, 'eta_pickup_predicted_mins', None) is not None:
            actual = max(0, int(round((ride.started_at - ride.accepted_at).total_seconds() / 60.0)))
            pred = int(ride.eta_pickup_predicted_mins or 0)
            err = abs(actual - pred)
            ETA_ABS_ERR_MIN.observe(float(err))
    except Exception:
        pass
    background_tasks.add_task(
        ride_ws_manager.broadcast_ride_status,
        ride_id,
        {
            "type": "ride_status",
            "ride_id": ride_id,
            "status": ride.status,
            "rider_user_id": str(ride.rider_user_id),
            "driver_id": str(ride.driver_id) if ride.driver_id else None,
            "quoted_fare_cents": ride.quoted_fare_cents,
            "final_fare_cents": ride.final_fare_cents,
            "distance_km": ride.distance_km,
        },
    )
    # Push notify rider on start
    try:
        send_push_to_user(db, str(ride.rider_user_id), "Ride started", "Trip is in progress", app_mode="rider")
    except Exception:
        pass
    return {"detail": "enroute"}


@router.post("/{ride_id}/complete", response_model=RideOut)
def complete_ride(
    ride_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    drv = _get_driver_for_user(db, user)
    if is_suspended_driver(db, str(drv.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="driver_suspended")
    ride = (
        db.query(Ride)
        .filter(Ride.id == ride_id)
        .with_for_update()
        .one_or_none()
    )
    if ride is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    if ride.driver_id != drv.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your ride")
    prev = ride.status
    just_completed = False
    if ride.status == "completed":
        # idempotent
        pass
    else:
        if ride.status != "enroute":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status transition")
        # Fraud: enforce driver near dropoff at completion
        try:
            loc_age = getattr(settings, "FRAUD_DRIVER_LOC_MAX_AGE_SECS", 300)
            max_comp_km = getattr(settings, "FRAUD_MAX_COMPLETE_DIST_KM", 0.5)
            require_driver_location_fresh_and_near(db, drv, target_lat=ride.dropoff_lat, target_lon=ride.dropoff_lon, max_age_secs=int(loc_age), max_dist_km=float(max_comp_km), stage="complete")
        except HTTPException:
            raise
        prev = ride.status
        ride.status = "completed"
        ride.completed_at = datetime.now(timezone.utc)
        # For MVP final fare equals quote
        ride.final_fare_cents = ride.quoted_fare_cents
        drv.status = "available"
        just_completed = True

    if just_completed:
        interval = max(1, int(getattr(settings, "LOYALTY_RIDE_INTERVAL", 10)))
        try:
            rider_user = (
                db.query(User)
                .filter(User.id == ride.rider_user_id)
                .with_for_update()
                .one()
            )
        except Exception:
            rider_user = None
        try:
            driver_user = (
                db.query(User)
                .filter(User.id == drv.user_id)
                .with_for_update()
                .one()
            )
        except Exception:
            driver_user = None

        if rider_user is not None:
            rider_count = int(getattr(rider_user, "rider_loyalty_count", 0) or 0) + 1
            if rider_count >= interval:
                cap = int(getattr(settings, "LOYALTY_RIDER_FREE_CAP_CENTS", 50000) or 0)
                if (ride.final_fare_cents or 0) <= cap:
                    ride.final_fare_cents = 0
                    ride.rider_reward_applied = True
                rider_count = 0
            rider_user.rider_loyalty_count = rider_count

        if driver_user is not None:
            driver_count = int(getattr(driver_user, "driver_loyalty_count", 0) or 0) + 1
            if driver_count >= interval:
                ride.driver_reward_fee_waived = True
                driver_count = 0
            driver_user.driver_loyalty_count = driver_count
    db.flush()
    _count_transition(prev, ride.status)
    # Cash ride & escrow release: if used, release escrow to driver on successful completion
    payment_request_id = None
    platform_fee_cents: int | None = None
    reward_fee_credit = 0
    driver_reward_current = bool(getattr(ride, "driver_reward_fee_waived", False))
    try:
        if ride.final_fare_cents is not None:
            # Compute fee
            fee_bps = settings.PLATFORM_FEE_BPS
            fee = 0
            if fee_bps and ride.final_fare_cents:
                fee = int((ride.final_fare_cents * fee_bps + 5000) // 10000)
            if driver_reward_current:
                reward_fee_credit = fee
                fee = 0
            platform_fee_cents = fee
            if fee > 0:
                # When Taxi Wallet is enabled, the fee was already debited at accept.
                # For legacy mode (Taxi Wallet disabled), keep direct debit from Payments main wallet.
                if not getattr(settings, "TAXI_WALLET_ENABLED", True):
                    # Legacy path: direct debit from Payments main wallet
                    try:
                        driver_user = db.query(User).join(Driver, Driver.user_id == User.id).filter(Driver.id == ride.driver_id).one()
                        fee_payload = {
                            "from_phone": driver_user.phone,
                            "to_phone": settings.FEE_WALLET_PHONE,
                            "amount_cents": fee,
                        }
                        from superapp_shared.internal_hmac import sign_internal_request_headers
                        headers2 = sign_internal_request_headers(fee_payload, settings.PAYMENTS_INTERNAL_SECRET, request.headers.get("X-Request-ID", ""))
                        headers2["X-Idempotency-Key"] = f"taxi:{ride.id}:fee"
                        with httpx.Client(timeout=5.0) as client:
                            client.post(
                                f"{settings.PAYMENTS_BASE_URL}/internal/transfer",
                                headers=headers2,
                                json=fee_payload,
                            )
                    except Exception:
                        pass
    except Exception:
        pass

    should_credit_wallet = (
        just_completed
        and getattr(settings, "TAXI_WALLET_ENABLED", True)
        and (
            driver_reward_current
            or (ride.final_fare_cents or 0) == 0
        )
    )
    if should_credit_wallet:
        try:
            w = db.query(TaxiWallet).filter(TaxiWallet.driver_id == drv.id).with_for_update().one_or_none()
            if w is None:
                w = TaxiWallet(driver_id=drv.id, balance_cents=0)
                db.add(w)
                db.flush()
            entry = (
                db.query(TaxiWalletEntry)
                .filter(
                    TaxiWalletEntry.wallet_id == w.id,
                    TaxiWalletEntry.ride_id == ride.id,
                    TaxiWalletEntry.type == "fee",
                )
                .one_or_none()
            )
            amount_to_credit = 0
            if entry is not None:
                amount_to_credit = max(0, -int(entry.amount_cents_signed or 0))
            if amount_to_credit == 0 and reward_fee_credit > 0:
                amount_to_credit = reward_fee_credit
            if amount_to_credit > 0:
                w.balance_cents += amount_to_credit
                entry_type = "reward" if driver_reward_current else "refund"
                reason = "driver_loyalty_fee_waiver" if driver_reward_current else "rider_free_ride"
                db.add(
                    TaxiWalletEntry(
                        wallet_id=w.id,
                        type=entry_type,
                        amount_cents_signed=amount_to_credit,
                        ride_id=ride.id,
                        original_fare_cents=ride.final_fare_cents,
                        fee_cents=0,
                        driver_take_home_cents=max(0, (ride.final_fare_cents or 0)),
                        meta={"reason": reason, "reimbursed_fee_cents": amount_to_credit},
                    )
                )
        except Exception:
            pass

    # Release escrow to driver main wallet (if any)
    try:
        if getattr(settings, "TAXI_ESCROW_WALLET_PHONE", None) and (ride.escrow_amount_cents or 0) > 0 and not bool(getattr(ride, "escrow_released", False)) and pay_allowed("escrow_release"):
            # Find driver phone
            if ride.driver_id:
                driver_user = db.query(User).join(Driver, Driver.user_id == User.id).filter(Driver.id == ride.driver_id).one_or_none()
                if driver_user is not None:
                    amt = int(ride.escrow_amount_cents or 0)
                    body = {"from_phone": settings.TAXI_ESCROW_WALLET_PHONE, "to_phone": driver_user.phone, "amount_cents": amt}
                    from superapp_shared.internal_hmac import sign_internal_request_headers
                    headers2 = sign_internal_request_headers(body, settings.PAYMENTS_INTERNAL_SECRET, request.headers.get("X-Request-ID", ""))
                    headers2["X-Idempotency-Key"] = f"taxi:{ride.id}:escrow_release"
                    import httpx as _httpx
                    with _httpx.Client(timeout=5.0) as client:
                        r = client.post(f"{settings.PAYMENTS_BASE_URL}/internal/transfer", json=body, headers=headers2)
                        pay_record("escrow_release", r.status_code < 400)
                        if r.status_code < 400:
                            ride.escrow_released = True
                        else:
                            # Fallback: create internal payment request escrow -> driver
                            try:
                                headers_req = sign_internal_request_headers(body, settings.PAYMENTS_INTERNAL_SECRET, request.headers.get("X-Request-ID", ""))
                                client.post(f"{settings.PAYMENTS_BASE_URL}/internal/requests", json=body, headers=headers_req)
                            except Exception:
                                pass
    except Exception:
        pass

    payload = {
        "type": "ride_status",
        "ride_id": ride_id,
        "status": ride.status,
        "rider_user_id": str(ride.rider_user_id),
        "driver_id": str(ride.driver_id) if ride.driver_id else None,
        "quoted_fare_cents": ride.quoted_fare_cents,
        "final_fare_cents": ride.final_fare_cents,
        "distance_km": ride.distance_km,
        "rider_reward_applied": bool(getattr(ride, "rider_reward_applied", False)),
        "driver_reward_fee_waived": bool(getattr(ride, "driver_reward_fee_waived", False)),
    }
    background_tasks.add_task(ride_ws_manager.broadcast_ride_status, ride_id, payload)
    # Notify driver channel about completion
    try:
        import anyio
        if ride.driver_id:
            anyio.from_thread.run(driver_ws_manager.broadcast_to_driver, str(ride.driver_id), {"type": "ride_completed", "ride_id": str(ride.id)})
    except Exception:
        pass

    return RideOut(
        id=str(ride.id),
        status=ride.status,
        rider_user_id=str(ride.rider_user_id),
        driver_id=str(ride.driver_id) if ride.driver_id else None,
        quoted_fare_cents=ride.quoted_fare_cents,
        final_fare_cents=ride.final_fare_cents,
        distance_km=ride.distance_km,
        payment_request_id=payment_request_id,
        platform_fee_cents=platform_fee_cents,
        ride_class=getattr(payload, 'ride_class', None),
        pickup_lat=ride.pickup_lat,
        pickup_lon=ride.pickup_lon,
        dropoff_lat=ride.dropoff_lat,
        dropoff_lon=ride.dropoff_lon,
        created_at=ride.created_at,
        started_at=ride.started_at,
        completed_at=ride.completed_at,
        rider_reward_applied=bool(getattr(ride, "rider_reward_applied", False)),
        driver_reward_fee_waived=bool(getattr(ride, "driver_reward_fee_waived", False)),
    )


@router.get("", response_model=RidesListOut)
def list_my_rides(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Ride)
    if user.role == "driver":
        drv = _get_driver_for_user(db, user)
        q = q.filter(Ride.driver_id == drv.id)
    else:
        q = q.filter(Ride.rider_user_id == user.id)
    rides = q.order_by(Ride.created_at.desc()).limit(100).all()
    out = []
    for r in rides:
        stops = db.query(RideStop).filter(RideStop.ride_id == r.id).order_by(RideStop.seq.asc()).all()
        rating = (
            db.query(RideRating)
            .filter(RideRating.ride_id == r.id, RideRating.rider_user_id == user.id)
            .one_or_none()
        )
        out.append(
            RideOut(
                id=str(r.id),
                status=r.status,
                rider_user_id=str(r.rider_user_id),
                driver_id=str(r.driver_id) if r.driver_id else None,
                quoted_fare_cents=r.quoted_fare_cents,
                final_fare_cents=r.final_fare_cents,
                distance_km=r.distance_km,
                ride_class=getattr(r, 'ride_class', None),
                stops=[{"lat": s.lat, "lon": s.lon} for s in stops] or None,
                pickup_lat=r.pickup_lat,
                pickup_lon=r.pickup_lon,
                dropoff_lat=r.dropoff_lat,
                dropoff_lon=r.dropoff_lon,
                created_at=r.created_at,
                started_at=r.started_at,
                completed_at=r.completed_at,
                rider_reward_applied=getattr(r, 'rider_reward_applied', False),
                driver_reward_fee_waived=getattr(r, 'driver_reward_fee_waived', False),
                my_rating=rating.rating if rating else None,
                my_rating_comment=rating.comment if rating else None,
                my_rating_created_at=rating.created_at if rating else None,
            )
        )
    return RidesListOut(rides=out)


@router.post("/{ride_id}/cancel_by_rider")
def cancel_by_rider(ride_id: str, background_tasks: BackgroundTasks, payload: CancelIn | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ride = (
        db.query(Ride)
        .filter(Ride.id == ride_id)
        .with_for_update()
        .one_or_none()
    )
    if ride is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    if ride.rider_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your ride")
    if ride.status in ("completed",):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot cancel completed ride")
    prev = ride.status
    ride.status = "requested"  # mark back to requested (MVP), driver will be freed if any
    if ride.driver_id:
        drv = db.get(Driver, ride.driver_id)
        if drv:
            drv.status = "available"
        ride.driver_id = None
    db.flush()
    _count_transition(prev, ride.status)
    # If fare was prepaid into escrow, attempt refund to rider main wallet
    try:
        amt = int(getattr(ride, "escrow_amount_cents", 0) or 0)
        if amt > 0 and getattr(settings, "TAXI_ESCROW_WALLET_PHONE", None) and settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and pay_allowed("escrow_refund"):
            rider_user = db.get(User, ride.rider_user_id)
            if rider_user is not None and rider_user.phone:
                body = {"from_phone": settings.TAXI_ESCROW_WALLET_PHONE, "to_phone": rider_user.phone, "amount_cents": amt}
                from superapp_shared.internal_hmac import sign_internal_request_headers
                headers2 = sign_internal_request_headers(body, settings.PAYMENTS_INTERNAL_SECRET, None)
                headers2["X-Idempotency-Key"] = f"taxi:{ride.id}:escrow_refund"
                import httpx as _httpx
                with _httpx.Client(timeout=5.0) as client:
                    r = client.post(f"{settings.PAYMENTS_BASE_URL}/internal/transfer", json=body, headers=headers2)
                    pay_record("escrow_refund", r.status_code < 400)
                    if r.status_code < 400:
                        # Clear escrow so later release does not trigger
                        ride.escrow_amount_cents = 0
                    else:
                        # Fallback: create internal payment request escrow -> rider (best effort)
                        try:
                            headers_req = sign_internal_request_headers(body, settings.PAYMENTS_INTERNAL_SECRET, None)
                            client.post(f"{settings.PAYMENTS_BASE_URL}/internal/requests", json=body, headers=headers_req)
                        except Exception:
                            pass
    except Exception:
        # Do not fail cancellation on refund errors; client can reattempt or resolve via support.
        pass
    background_tasks.add_task(ride_ws_manager.broadcast_ride_status, ride_id, {"type": "ride_status", "ride_id": ride_id, "status": ride.status})
    # fraud: track cancel event (for later ratios)
    try:
        record_fraud_event(db, user_id=str(user.id), type="rider.cancel", data={"ride_id": ride_id})
    except Exception:
        pass
    return {"detail": "canceled"}


@router.post("/{ride_id}/cancel_by_driver")
def cancel_by_driver(ride_id: str, background_tasks: BackgroundTasks, payload: CancelIn | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    drv = _get_driver_for_user(db, user)
    ride = (
        db.query(Ride)
        .filter(Ride.id == ride_id)
        .with_for_update()
        .one_or_none()
    )
    if ride is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    if ride.driver_id != drv.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your ride")
    if ride.status in ("completed",):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot cancel completed ride")
    # free driver and try reassignment
    drv.status = "available"
    ride.driver_id = None
    prev = ride.status
    ride.status = "requested"
    # Reassign to nearest available
    fee_bps = settings.PLATFORM_FEE_BPS
    required_fee = int(((ride.quoted_fare_cents or 0) * fee_bps + 5000) // 10000) if fee_bps else 0
    new_drv = _find_nearest_available_driver(db, ride.pickup_lat, ride.pickup_lon, required_fee)
    if new_drv:
        _assign_driver(db, ride, new_drv)
    db.flush()
    _count_transition(prev, ride.status)
    # If no reassignment happened and fare was prepaid into escrow, attempt refund to rider
    try:
        if not ride.driver_id:
            amt = int(getattr(ride, "escrow_amount_cents", 0) or 0)
            if amt > 0 and getattr(settings, "TAXI_ESCROW_WALLET_PHONE", None) and settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and pay_allowed("escrow_refund"):
                rider_user = db.get(User, ride.rider_user_id)
                if rider_user is not None and rider_user.phone:
                    body = {"from_phone": settings.TAXI_ESCROW_WALLET_PHONE, "to_phone": rider_user.phone, "amount_cents": amt}
                    from superapp_shared.internal_hmac import sign_internal_request_headers
                    headers2 = sign_internal_request_headers(body, settings.PAYMENTS_INTERNAL_SECRET, None)
                    headers2["X-Idempotency-Key"] = f"taxi:{ride.id}:escrow_refund_driver"
                    import httpx as _httpx
                    with _httpx.Client(timeout=5.0) as client:
                        r = client.post(f"{settings.PAYMENTS_BASE_URL}/internal/transfer", json=body, headers=headers2)
                        pay_record("escrow_refund", r.status_code < 400)
                        if r.status_code < 400:
                            ride.escrow_amount_cents = 0
                        else:
                            try:
                                headers_req = sign_internal_request_headers(body, settings.PAYMENTS_INTERNAL_SECRET, None)
                                client.post(f"{settings.PAYMENTS_BASE_URL}/internal/requests", json=body, headers=headers_req)
                            except Exception:
                                pass
    except Exception:
        pass
    try:
        REASSIGN_EVENTS.labels("driver_cancel", "assigned" if ride.driver_id else "none").inc()
    except Exception:
        pass
    background_tasks.add_task(
        ride_ws_manager.broadcast_ride_status,
        ride_id,
        {
            "type": "ride_status",
            "ride_id": ride_id,
            "status": ride.status,
            "driver_id": str(ride.driver_id) if ride.driver_id else None,
        },
    )
    return {"detail": "reassigned" if ride.driver_id else "canceled"}


@router.post("/{ride_id}/reassign")
def reassign_ride(ride_id: str, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Allow rider or the currently assigned driver to trigger reassignment
    ride = (
        db.query(Ride)
        .filter(Ride.id == ride_id)
        .with_for_update()
        .one_or_none()
    )
    if ride is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    if ride.rider_user_id != user.id and not (ride.driver_id and db.get(Driver, ride.driver_id).user_id == user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if ride.status not in ("requested", "assigned"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot reassign at this stage")
    # free current driver if any
    if ride.driver_id:
        cur = db.get(Driver, ride.driver_id)
        if cur:
            cur.status = "available"
        ride.driver_id = None
        prev = ride.status
        ride.status = "requested"
        _count_transition(prev, ride.status)
    # reassign
    fee_bps = settings.PLATFORM_FEE_BPS
    required_fee = int(((ride.quoted_fare_cents or 0) * fee_bps + 5000) // 10000) if fee_bps else 0
    new_drv = _find_nearest_available_driver(
        db,
        ride.pickup_lat,
        ride.pickup_lon,
        required_fee,
        relax_min_balance=False,
        radius_km=float(getattr(settings, "ASSIGN_RADIUS_KM", 5)) * float(getattr(settings, "REASSIGN_RADIUS_FACTOR", 1.0)),
    )
    if new_drv:
        _assign_driver(db, ride, new_drv)
    db.flush()
    try:
        REASSIGN_EVENTS.labels("rider_request", "assigned" if ride.driver_id else "none").inc()
    except Exception:
        pass
    background_tasks.add_task(ride_ws_manager.broadcast_ride_status, ride_id, {"type": "ride_status", "ride_id": ride_id, "status": ride.status, "driver_id": str(ride.driver_id) if ride.driver_id else None})
    return {"detail": "reassigned" if ride.driver_id else "no_driver"}


@router.post("/reassign_stale")
def reassign_stale(
    background_tasks: BackgroundTasks,
    minutes: int = 2,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # DEV helper: scan requested/assigned older than threshold and try reassignment
    from datetime import datetime, timedelta
    if settings.ENV != "dev":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    candidates = (
        db.query(Ride)
        .filter(Ride.created_at <= cutoff)
        .filter(Ride.status.in_(["requested", "assigned"]))
        .all()
    )
    count = 0
    for ride in candidates:
        # if assigned but driver busy, skip; try to improve only if no driver or driver is offline
        if ride.status == "assigned" and ride.driver_id:
            drv = db.get(Driver, ride.driver_id)
            if drv and drv.status == "busy":
                continue
            if drv:
                drv.status = "available"
            ride.driver_id = None
            prev = ride.status
            ride.status = "requested"
            _count_transition(prev, ride.status)
        new_drv = _find_nearest_available_driver(
            db,
            ride.pickup_lat,
            ride.pickup_lon,
            None,
            relax_min_balance=bool(getattr(settings, "REASSIGN_RELAX_WALLET", False)),
            radius_km=float(getattr(settings, "ASSIGN_RADIUS_KM", 5)) * float(getattr(settings, "REASSIGN_RADIUS_FACTOR", 1.0)),
        )
        if new_drv and _assign_driver(db, ride, new_drv):
            count += 1
            background_tasks.add_task(
                ride_ws_manager.broadcast_ride_status,
                str(ride.id),
                {"type": "ride_status", "ride_id": str(ride.id), "status": ride.status, "driver_id": str(ride.driver_id)},
            )
            try:
                REASSIGN_EVENTS.labels("stale_scan", "assigned").inc()
            except Exception:
                pass
        else:
            try:
                REASSIGN_EVENTS.labels("stale_scan", "none").inc()
            except Exception:
                pass
    return {"reassigned": count, "scanned": len(candidates)}


def _is_admin_token_valid(incoming: str | None) -> bool:
    if not incoming:
        return False
    token_plain = getattr(settings, "ADMIN_TOKEN", "")
    for candidate in [t.strip() for t in token_plain.split(',') if t.strip()]:
        if secrets.compare_digest(incoming, candidate):
            return True
    digest = hashlib.sha256(incoming.encode()).hexdigest().lower()
    for candidate in settings.admin_token_hashes:
        if secrets.compare_digest(digest, candidate.lower()):
            return True
    return False


def _require_admin(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"), request: Request = None):
    if not _is_admin_token_valid(x_admin_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin token invalid")
    allow = os.getenv("ADMIN_IP_ALLOWLIST", getattr(settings, "ADMIN_IP_ALLOWLIST", ""))
    if allow:
        ips = [ip.strip() for ip in allow.split(',') if ip.strip()]
        host = None
        try:
            if request and request.client:
                host = request.client.host
        except Exception:
            host = None
        if host and host not in ips:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_ip_blocked")


@router.post("/reap_timeouts")
def reap_timeouts(
    background_tasks: BackgroundTasks,
    accept_timeout_secs: int | None = None,
    limit: int | None = None,
    relax_wallet: bool | None = None,
    _: None = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Reap assigned rides that have not been accepted within timeout and try reassignment.

    Intended to be invoked periodically (cron). Uses created_at as baseline for MVP.
    """
    from datetime import datetime, timedelta
    acc_to = int(accept_timeout_secs or getattr(settings, "ASSIGNMENT_ACCEPT_TIMEOUT_SECS", 120))
    lim = int(limit or getattr(settings, "REASSIGN_SCAN_LIMIT", 200))
    relax = bool(relax_wallet if relax_wallet is not None else getattr(settings, "REASSIGN_RELAX_WALLET", False))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=acc_to)
    q = (
        db.query(Ride)
        .filter(Ride.created_at <= cutoff)
        .filter(Ride.status == "assigned")
        .order_by(Ride.created_at.asc())
    )
    if lim > 0:
        q = q.limit(lim)
    items = q.all()
    reassigned = 0
    for ride in items:
        # free current driver
        if ride.driver_id:
            cur = db.get(Driver, ride.driver_id)
            if cur:
                cur.status = "available"
        ride.driver_id = None
        prev = ride.status
        ride.status = "requested"
        _count_transition(prev, ride.status)
        fee_bps = settings.PLATFORM_FEE_BPS
        required_fee = int(((ride.quoted_fare_cents or 0) * fee_bps + 5000) // 10000) if fee_bps else 0
        new_drv = _find_nearest_available_driver(
            db,
            ride.pickup_lat,
            ride.pickup_lon,
            required_fee,
            relax_min_balance=relax,
            radius_km=float(getattr(settings, "ASSIGN_RADIUS_KM", 5)) * float(getattr(settings, "REASSIGN_RADIUS_FACTOR", 1.0)),
        )
        if new_drv and _assign_driver(db, ride, new_drv):
            reassigned += 1
            try:
                TIMEOUT_REAPED.labels("accept_timeout", "assigned").inc()
            except Exception:
                pass
            background_tasks.add_task(
                ride_ws_manager.broadcast_ride_status,
                str(ride.id),
                {"type": "ride_status", "ride_id": str(ride.id), "status": ride.status, "driver_id": str(ride.driver_id)},
            )
        else:
            try:
                TIMEOUT_REAPED.labels("accept_timeout", "none").inc()
            except Exception:
                pass
    return {"reassigned": reassigned, "scanned": len(items), "accept_timeout_secs": acc_to}


@router.post("/reap_start_timeouts")
def reap_start_timeouts(
    background_tasks: BackgroundTasks,
    start_timeout_secs: int | None = None,
    limit: int | None = None,
    relax_wallet: bool | None = None,
    _: None = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Reap accepted rides that did not transition to enroute within timeout and try reassignment."""
    from datetime import datetime, timedelta
    st_to = int(start_timeout_secs or getattr(settings, "ACCEPTED_START_TIMEOUT_SECS", 300))
    lim = int(limit or getattr(settings, "REASSIGN_SCAN_LIMIT", 200))
    relax = bool(relax_wallet if relax_wallet is not None else getattr(settings, "REASSIGN_RELAX_WALLET", False))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=st_to)
    q = (
        db.query(Ride)
        .filter(Ride.status == "accepted")
        .filter(Ride.accepted_at != None)  # noqa: E711
        .filter(Ride.accepted_at <= cutoff)
        .order_by(Ride.accepted_at.asc())
    )
    if lim > 0:
        q = q.limit(lim)
    items = q.all()
    reassigned = 0
    for ride in items:
        # free current driver
        if ride.driver_id:
            cur = db.get(Driver, ride.driver_id)
            if cur:
                cur.status = "available"
        ride.driver_id = None
        prev = ride.status
        ride.status = "requested"
        _count_transition(prev, ride.status)
        fee_bps = settings.PLATFORM_FEE_BPS
        required_fee = int(((ride.quoted_fare_cents or 0) * fee_bps + 5000) // 10000) if fee_bps else 0
        new_drv = _find_nearest_available_driver(
            db,
            ride.pickup_lat,
            ride.pickup_lon,
            required_fee,
            relax_min_balance=relax,
            radius_km=float(getattr(settings, "ASSIGN_RADIUS_KM", 5)) * float(getattr(settings, "REASSIGN_RADIUS_FACTOR", 1.0)),
        )
        if new_drv and _assign_driver(db, ride, new_drv):
            reassigned += 1
            try:
                TIMEOUT_REAPED.labels("start_timeout", "assigned").inc()
            except Exception:
                pass
            background_tasks.add_task(
                ride_ws_manager.broadcast_ride_status,
                str(ride.id),
                {"type": "ride_status", "ride_id": str(ride.id), "status": ride.status, "driver_id": str(ride.driver_id)},
            )
        else:
            try:
                TIMEOUT_REAPED.labels("start_timeout", "none").inc()
            except Exception:
                pass
    return {"reassigned": reassigned, "scanned": len(items), "start_timeout_secs": st_to}


@router.post("/{ride_id}/rate")
def rate_ride(ride_id: str, payload: RideRatingIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ride = db.get(Ride, ride_id)
    if ride is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    if ride.rider_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your ride")
    if ride.status != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ride not completed")
    exists = db.query(RideRating).filter(RideRating.ride_id == ride.id).one_or_none()
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already rated")
    if not ride.driver_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No driver to rate")
    rating = RideRating(
        ride_id=ride.id,
        rider_user_id=ride.rider_user_id,
        driver_id=ride.driver_id,
        rating=payload.rating,
        comment=payload.comment or None,
    )
    db.add(rating)
    db.flush()
    agg = db.query(func.avg(RideRating.rating), func.count(RideRating.id)).filter(RideRating.driver_id == ride.driver_id).one()
    avg_rating = float(agg[0]) if agg[0] is not None else None
    count = int(agg[1] or 0)
    return {"detail": "ok", "avg_rating": avg_rating, "ratings_count": count}


@router.get("/{ride_id}/receipt", response_model=RideReceiptOut)
def get_ride_receipt(ride_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Visibility: rider or the driver of the ride
    ride = db.get(Ride, ride_id)
    if ride is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    allowed = (ride.rider_user_id == user.id) or (ride.driver_id is not None and db.get(Driver, ride.driver_id).user_id == user.id)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    # Fetch phones
    rider = db.get(User, ride.rider_user_id)
    drv_phone = None
    if ride.driver_id:
        drv = db.get(Driver, ride.driver_id)
        if drv:
            drv_user = db.get(User, drv.user_id)
            drv_phone = drv_user.phone if drv_user else None
    fare = int(ride.final_fare_cents or ride.quoted_fare_cents or 0)
    try:
        fee_bps = int(getattr(settings, "PLATFORM_FEE_BPS", 0) or 0)
    except Exception:
        fee_bps = 0
    fee = int(((fare * fee_bps) + 5000) // 10000) if (fee_bps and fare) else 0
    take_home = max(0, fare - fee)
    # Payment method/status heuristic (no external lookups)
    method = "cash"
    status = "cash"
    escrow_amt = int(getattr(ride, "escrow_amount_cents", 0) or 0)
    escrow_released = bool(getattr(ride, "escrow_released", False))
    if getattr(ride, "payer_mode", None) == "cash":
        method = "cash"; status = "cash"
    else:
        # treat as escrow flow if any escrow was recorded
        if escrow_amt > 0 or escrow_released:
            method = "escrow"
            status = "released" if escrow_released else "held"
        else:
            method = "unknown"; status = "unknown"
    return {
        "ride_id": ride_id,
        "created_at": ride.created_at,
        "completed_at": ride.completed_at,
        "rider_phone": rider.phone if rider else None,
        "driver_phone": drv_phone,
        "passenger_name": getattr(ride, "passenger_name", None),
        "passenger_phone": getattr(ride, "passenger_phone", None),
        "pay_mode": getattr(ride, "payer_mode", None),
        "payment_method": method,
        "payment_status": status,
        "fare_cents": fare,
        "platform_fee_cents": fee,
        "driver_take_home_cents": take_home,
        "distance_km": ride.distance_km,
        "escrow_amount_cents": escrow_amt,
        "escrow_released": escrow_released,
        "rider_reward_applied": bool(getattr(ride, "rider_reward_applied", False)),
        "driver_reward_fee_waived": bool(getattr(ride, "driver_reward_fee_waived", False)),
    }
