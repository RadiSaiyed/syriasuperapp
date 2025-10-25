from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from math import radians, cos, sin, asin, sqrt
from ..auth import get_current_user, get_db
from ..models import Zone, Tariff


router = APIRouter(prefix="/zones", tags=["zones"])


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # approximate radius of earth in km
    R = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


class ZoneNearRes(BaseModel):
    id: str
    name: str
    distance_m: int
    tariff_per_minute_cents: int
    service_fee_bps: int
    currency: str
    min_minutes: int | None = None
    free_minutes: int | None = None
    max_daily_cents: int | None = None


@router.get("/near", response_model=ZoneNearRes)
def zone_near(lat: float, lon: float, db: Session = Depends(get_db), user=Depends(get_current_user)):
    zs = db.query(Zone).all()
    if not zs:
        raise HTTPException(404, "no_zones")
    # Pick nearest center
    nearest = min(zs, key=lambda z: _haversine_km(lat, lon, z.center_lat, z.center_lon))
    dist_km = _haversine_km(lat, lon, nearest.center_lat, nearest.center_lon)
    t = db.query(Tariff).filter(Tariff.zone_id == nearest.id).first()
    if not t:
        raise HTTPException(400, "tariff_missing")
    return ZoneNearRes(
        id=str(nearest.id),
        name=nearest.name,
        distance_m=int(dist_km * 1000),
        tariff_per_minute_cents=t.per_minute_cents,
        service_fee_bps=t.service_fee_bps or 0,
        currency=t.currency or "SYP",
        min_minutes=t.min_minutes,
        free_minutes=t.free_minutes,
        max_daily_cents=t.max_daily_cents,
    )
