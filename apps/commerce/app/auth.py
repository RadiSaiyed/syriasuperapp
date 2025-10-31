import os
import datetime as dt
import jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from .models import User


bearer_scheme = HTTPBearer(auto_error=True)


def create_access_token(user_id: str, phone: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": user_id,
        "phone": phone,
        "iat": int(now.timestamp()),
        "exp": int((now + settings.jwt_expires_delta).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    token = creds.credentials
    try:
        jwks_url = os.getenv("JWT_JWKS_URL")
        if jwks_url:
            from superapp_shared.jwks_verify import decode_with_jwks
            aud = os.getenv("JWT_AUDIENCE") if os.getenv("JWT_VALIDATE_AUD", "false").lower() == "true" else None
            iss = os.getenv("JWT_ISSUER") if os.getenv("JWT_VALIDATE_ISS", "false").lower() == "true" else None
            payload = decode_with_jwks(token, jwks_url, audience=aud, issuer=iss)
        else:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = db.get(User, user_id)
    if not user:
        # Auto-provision on first JWT use (when using JWKS SSO)
        try:
            phone = (payload.get("phone") or "").strip()
            name = (payload.get("name") or None)
            if phone:
                user = User(id=user_id, phone=phone, name=name)
                db.add(user)
                db.flush()
        except Exception:
            pass
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
