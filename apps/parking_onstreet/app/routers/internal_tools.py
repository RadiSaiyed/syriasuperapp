from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta

from ..auth import get_current_user, get_db
from ..models import User, Session as ParkSession, Vehicle, Tariff
from ..config import settings
from ..pricing import compute_fee
from superapp_shared.internal_hmac import verify_internal_hmac_with_replay


router = APIRouter(prefix="/internal/tools", tags=["internal_tools"])  # HMAC + user auth required


class StartParkingIn(BaseModel):
    user_id: str
    zone_id: str
    plate: str
    minutes: int | None = None


class StartParkingOut(BaseModel):
    session_id: str
    started_at: datetime
    assumed_end_at: datetime | None = None
    prepaid_minutes: int | None = None


@router.post("/start_parking", response_model=StartParkingOut)
def start_parking(payload: StartParkingIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ts = request.headers.get("X-Internal-Ts") or ""
    sign = request.headers.get("X-Internal-Sign") or ""
    ok = verify_internal_hmac_with_replay(ts, payload.model_dump(), sign, settings.INTERNAL_API_SECRET, redis_url=settings.REDIS_URL, ttl_secs=60)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if str(user.id) != str(payload.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: user mismatch")

    veh = db.query(Vehicle).filter_by(user_id=user.id, plate=payload.plate).first()
    if not veh:
        veh = Vehicle(user_id=user.id, plate=payload.plate)
        db.add(veh)
        db.flush()
    t = db.query(Tariff).filter(Tariff.zone_id == payload.zone_id).first()
    if not t:
        raise HTTPException(status_code=400, detail="tariff_missing")
    s = ParkSession(user_id=user.id, vehicle_id=veh.id, zone_id=payload.zone_id)
    # If minutes provided, set assumed end and prepaid
    if payload.minutes and payload.minutes > 0:
        s.assumed_end_at = s.started_at + timedelta(minutes=int(payload.minutes))
        s.prepaid_minutes = int(payload.minutes)
    db.add(s)
    db.flush()
    return StartParkingOut(session_id=str(s.id), started_at=s.started_at, assumed_end_at=s.assumed_end_at, prepaid_minutes=s.prepaid_minutes)

