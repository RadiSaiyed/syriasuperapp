from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from ..auth import get_current_user, get_db
from ..models import DeviceToken, User


router = APIRouter(prefix="/push", tags=["push"])


@router.post("/register")
def register_token(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    token = (payload.get("token") or "").strip()
    platform = (payload.get("platform") or "").strip().lower()  # android|ios|web
    app_mode = (payload.get("app_mode") or "").strip().lower() or None
    if not token or platform not in ("android", "ios", "web"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_token")
    row = db.query(DeviceToken).filter(DeviceToken.token == token).one_or_none()
    if row is None:
        row = DeviceToken(user_id=user.id, token=token, platform=platform, app_mode=app_mode, enabled=True, last_seen=datetime.utcnow(), updated_at=datetime.utcnow())
        db.add(row)
    else:
        row.user_id = user.id
        row.platform = platform
        row.app_mode = app_mode
        row.enabled = True
        row.last_seen = datetime.utcnow()
        row.updated_at = datetime.utcnow()
    db.flush()
    return {"detail": "ok"}


@router.post("/unregister")
def unregister_token(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    token = (payload.get("token") or "").strip()
    if not token:
        return {"detail": "ok"}
    row = db.query(DeviceToken).filter(DeviceToken.token == token).one_or_none()
    if row is not None:
        row.enabled = False
        row.updated_at = datetime.utcnow()
    db.flush()
    return {"detail": "ok"}

