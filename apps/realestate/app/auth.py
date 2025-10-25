from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from .database import get_db
from .models import User
from .config import settings
from datetime import datetime, timedelta
import jwt


def _make_token(user_id: str) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + settings.jwt_delta).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def _verify_dev_otp(phone: str, otp: str) -> bool:
    if settings.ENV.lower() == "dev" and settings.OTP_MODE.lower() == "dev":
        return otp == "123456"
    return False


def ensure_user(db: Session, phone: str, name: str | None) -> User:
    u = db.query(User).filter(User.phone == phone).one_or_none()
    if u is None:
        u = User(phone=phone, name=name or None)
        db.add(u)
        db.flush()
    return u


def get_current_user(authorization: str | None = Header(default=None, alias="Authorization"), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        uid = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    u = db.get(User, uid)
    if u is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    return u

