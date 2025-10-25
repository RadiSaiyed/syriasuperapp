from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Device
from ..schemas import PublishKeyIn, DeviceOut
from pydantic import BaseModel


router = APIRouter(prefix="/keys", tags=["keys"])


@router.post("/publish", response_model=DeviceOut)
def publish_key(payload: PublishKeyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Upsert device
    d = db.query(Device).filter(Device.user_id == user.id, Device.device_id == payload.device_id).one_or_none()
    if d is None:
        d = Device(user_id=user.id, device_id=payload.device_id, public_key=payload.public_key, device_name=payload.device_name or None, push_token=payload.push_token or None)
        db.add(d)
        db.flush()
    else:
        d.public_key = payload.public_key
        d.device_name = payload.device_name or d.device_name
        d.push_token = payload.push_token or d.push_token
    return DeviceOut(device_id=d.device_id, public_key=d.public_key, device_name=d.device_name, created_at=d.created_at)


@router.get("/{user_id}", response_model=list[DeviceOut])
def get_user_keys(user_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    devices = db.query(Device).filter(Device.user_id == user_id).order_by(Device.created_at.asc()).all()
    return [DeviceOut(device_id=d.device_id, public_key=d.public_key, device_name=d.device_name, created_at=d.created_at) for d in devices]


class DeviceUpdateIn(BaseModel):
    device_name: str | None = None
    push_token: str | None = None


@router.get("/me", response_model=list[DeviceOut])
def my_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Device).filter(Device.user_id == user.id).order_by(Device.created_at.asc()).all()
    return [DeviceOut(device_id=d.device_id, public_key=d.public_key, device_name=d.device_name, created_at=d.created_at) for d in rows]


@router.put("/devices/{device_id}")
def update_device(device_id: str, payload: DeviceUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.query(Device).filter(Device.user_id == user.id, Device.device_id == device_id).one_or_none()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    if payload.device_name is not None:
        d.device_name = payload.device_name
    if payload.push_token is not None:
        d.push_token = payload.push_token
    return {"detail": "ok"}


@router.delete("/devices/{device_id}")
def delete_device(device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.query(Device).filter(Device.user_id == user.id, Device.device_id == device_id).one_or_none()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    db.delete(d)
    return {"detail": "ok"}
