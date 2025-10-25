from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from ..auth import get_current_user, get_db
from ..models import Session as ParkSession, Vehicle, Tariff, Receipt
from ..pricing import compute_fee
from ..settlement import settle_with_payments
from ..config import settings
from math import radians, cos, sin, asin, sqrt


router = APIRouter(prefix="/sessions", tags=["sessions"])


class StartReq(BaseModel):
    plate: str
    zone_id: str


class StartRes(BaseModel):
    id: str
    started_at: datetime
    tariff_cents_per_min: int
    service_fee_bps: int
    currency: str


@router.post("/start", response_model=StartRes)
def start(req: StartReq, db: Session = Depends(get_db), user=Depends(get_current_user)):
    veh = db.query(Vehicle).filter_by(user_id=user.id, plate=req.plate).first()
    if not veh:
        veh = Vehicle(user_id=user.id, plate=req.plate)
        db.add(veh)
        db.flush()
    t = db.query(Tariff).filter(Tariff.zone_id == req.zone_id).first()
    if not t:
        raise HTTPException(400, "tariff_missing")
    s = ParkSession(user_id=user.id, vehicle_id=veh.id, zone_id=req.zone_id)
    db.add(s)
    db.flush()
    return StartRes(
        id=str(s.id),
        started_at=s.started_at,
        tariff_cents_per_min=t.per_minute_cents,
        service_fee_bps=t.service_fee_bps or 0,
        currency=t.currency or "SYP",
    )


class StopRes(BaseModel):
    id: str
    minutes: int
    gross_cents: int
    fee_cents: int
    net_cents: int


@router.post("/{sid}/stop", response_model=StopRes)
async def stop(sid: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.get(ParkSession, sid)
    if not s or s.user_id != user.id or s.status != "running":
        raise HTTPException(404, "session_invalid")
    t = db.query(Tariff).filter(Tariff.zone_id == s.zone_id).first()
    s.stopped_at = datetime.utcnow()
    minutes, gross, fee, net = compute_fee(s.started_at, s.stopped_at, t)
    # Membership discount (MVP): apply 5% discount on net if member has parking benefit
    try:
        import httpx
        from ..config import settings
        with httpx.Client(timeout=3.0) as client:
            r = client.get(f"{settings.AI_GATEWAY_BASE_URL}/v1/membership/status", params={"user_id": str(user.id), "phone": user.phone})
            if r.status_code < 400:
                tier = (r.json() or {}).get("tier", "none")
                bens = (r.json() or {}).get("benefits", []) or []
                if tier in ("prime", "basic") and any(b.startswith("parking_discount") for b in bens):
                    # find percentage from benefit name, default to 5
                    perc = 5
                    for b in bens:
                        if b.startswith("parking_discount_"):
                            try:
                                perc = int(b.split("_")[-1])
                            except Exception:
                                pass
                    discount = int(round(net * (perc / 100.0)))
                    net = max(0, net - discount)
    except Exception:
        pass
    s.minutes_billed, s.gross_cents, s.fee_cents, s.net_cents = minutes, gross, fee, net
    s.status = "stopped"
    # Create receipt if not exists
    existing = db.query(Receipt).filter(Receipt.session_id == s.id).one_or_none()
    if not existing:
        r = Receipt(
            session_id=s.id,
            minutes=minutes,
            gross_cents=gross,
            fee_cents=fee,
            net_cents=net,
            currency=t.currency or "SYP",
        )
        db.add(r)
    db.flush()
    # Attempt settlement via Payments (best-effort)
    try:
        await settle_with_payments(
            from_phone=user.phone,
            operator_phone=settings.OPERATOR_PHONE,
            fee_phone=settings.FEE_WALLET_PHONE,
            net_cents=net,
            fee_cents=fee,
        )
    except Exception:
        # Do not fail stop; operator reconciliation can happen later
        pass
    return StopRes(id=str(s.id), minutes=minutes, gross_cents=gross, fee_cents=fee, net_cents=net)


class MySession(BaseModel):
    id: str
    zone_id: str
    started_at: datetime
    status: str


@router.get("/my", response_model=list[MySession])
def my(status: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(ParkSession).filter(ParkSession.user_id == user.id)
    if status:
        q = q.filter(ParkSession.status == status)
    rows = q.order_by(ParkSession.started_at.desc()).limit(20).all()
    return [
        MySession(id=str(r.id), zone_id=str(r.zone_id), started_at=r.started_at, status=r.status)
        for r in rows
    ]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


class LocReq(BaseModel):
    lat: float
    lon: float
    buffer_m: int | None = 50


class LocRes(BaseModel):
    status: str
    auto_stopped: bool = False
    reason: str | None = None


@router.post("/{sid}/loc", response_model=LocRes)
async def update_loc(sid: str, req: LocReq, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.get(ParkSession, sid)
    if not s or s.user_id != user.id or s.status != "running":
        raise HTTPException(404, "session_invalid")
    # load zone center+radius via join on tariff -> session has zone_id
    t = db.query(Tariff).filter(Tariff.zone_id == s.zone_id).first()
    if not t:
        # find zone anyway through a roundtrip
        pass
    # fetch zone center/radius
    from ..models import Zone

    z: Zone | None = db.get(Zone, s.zone_id)
    if not z:
        return LocRes(status="unknown")
    dist_m = int(_haversine_km(req.lat, req.lon, z.center_lat, z.center_lon) * 1000)
    allowed = z.radius_m + (req.buffer_m or 0)
    if dist_m > allowed:
        # auto stop
        s.stopped_at = datetime.utcnow()
        minutes, gross, fee, net = compute_fee(s.started_at, s.stopped_at, t)
        s.minutes_billed, s.gross_cents, s.fee_cents, s.net_cents = minutes, gross, fee, net
        s.status = "stopped"
        s.auto_stopped_reason = "left_zone"
        existing = db.query(Receipt).filter(Receipt.session_id == s.id).one_or_none()
        if not existing:
            r = Receipt(
                session_id=s.id,
                minutes=minutes,
                gross_cents=gross,
                fee_cents=fee,
                net_cents=net,
                currency=t.currency or "SYP",
            )
            db.add(r)
        db.flush()
        try:
            await settle_with_payments(
                from_phone=user.phone,
                operator_phone=settings.OPERATOR_PHONE,
                fee_phone=settings.FEE_WALLET_PHONE,
                net_cents=net,
                fee_cents=fee,
            )
        except Exception:
            pass
        return LocRes(status="stopped", auto_stopped=True, reason="left_zone")
    return LocRes(status="running")


class ExtendReq(BaseModel):
    minutes: int = 15


class ExtendRes(BaseModel):
    session_id: str
    assumed_end_at: datetime
    prepaid_minutes: int | None


@router.post("/{sid}/extend", response_model=ExtendRes)
def extend(sid: str, req: ExtendReq, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.get(ParkSession, sid)
    if not s or s.user_id != user.id or s.status != "running":
        raise HTTPException(404, "session_invalid")
    add = max(1, int(req.minutes))
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    base = s.assumed_end_at or (now + timedelta(minutes=60))
    s.assumed_end_at = base + timedelta(minutes=add)
    s.prepaid_minutes = (s.prepaid_minutes or 0) + add
    db.flush()
    return ExtendRes(session_id=str(s.id), assumed_end_at=s.assumed_end_at, prepaid_minutes=s.prepaid_minutes)
