from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..ws_manager import ride_ws_manager, driver_ws_manager
from ..config import settings
import jwt
from ..database import SessionLocal
from ..models import Ride, RideStop, User, Driver


router = APIRouter()


@router.websocket("/ws/rides/{ride_id}")
async def ws_ride_status(websocket: WebSocket, ride_id: str):
    # Optional auth via token query (?token=JWT)
    token = websocket.query_params.get("token")
    if token:
        try:
            jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])  # could enforce membership to ride later
        except Exception:
            await websocket.close(code=4401)
            return
    await ride_ws_manager.connect(ride_id, websocket)
    try:
        # On connect, send current status once
        try:
            db = SessionLocal()
            ride = db.get(Ride, ride_id)
            if ride:
                stops = db.query(RideStop).filter(RideStop.ride_id == ride.id).order_by(RideStop.seq.asc()).all()
                payload = {
                    "type": "ride_status",
                    "ride_id": ride_id,
                    "status": ride.status,
                    "rider_user_id": str(ride.rider_user_id),
                    "driver_id": str(ride.driver_id) if ride.driver_id else None,
                    "quoted_fare_cents": ride.quoted_fare_cents,
                    "final_fare_cents": ride.final_fare_cents,
                    "distance_km": ride.distance_km,
                    "stops": [{"lat": s.lat, "lon": s.lon} for s in stops] or None,
                    "ts": datetime.utcnow().isoformat() + "Z",
                }
                await websocket.send_json(payload)
        except Exception:
            pass
        finally:
            try:
                db.close()
            except Exception:
                pass

        while True:
            # Keep connection alive; we don't expect messages from client
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ride_ws_manager.disconnect(ride_id, websocket)


@router.websocket("/ws/driver")
async def ws_driver(websocket: WebSocket):
    # Resolve current driver from token (?token=JWT)
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return
    driver_id = None
    try:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])  # default
        except Exception:
            # dev fallback: decode without signature to extract phone
            payload = jwt.decode(token, options={"verify_signature": False})
        sub = payload.get("sub")
        phone = payload.get("phone")
        db = SessionLocal()
        user = None
        if sub:
            user = db.get(User, sub)
        if not user and phone:
            user = db.query(User).filter(User.phone == phone).one_or_none()
        if not user:
            await websocket.close(code=4401)
            return
        drv = db.query(Driver).filter(Driver.user_id == user.id).one_or_none()
        if not drv:
            await websocket.close(code=4403)
            return
        driver_id = str(drv.id)
    except Exception:
        await websocket.close(code=4401)
        return
    await driver_ws_manager.connect(driver_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await driver_ws_manager.disconnect(driver_id, websocket)
