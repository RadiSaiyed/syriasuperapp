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
    now = dt.datetime.utcnow()
    payload = {
        "sub": user_id,
        "phone": phone,
        "iat": int(now.timestamp()),
        "exp": int((now + settings.jwt_expires_delta).timestamp()),
    }
    # Sign with current secret (first in list)
    signers = getattr(settings, 'JWT_SECRETS', None)
    secret = settings.JWT_SECRET
    try:
        if callable(signers):
            lst = settings.JWT_SECRETS()
        else:
            lst = settings.JWT_SECRETS if isinstance(settings.JWT_SECRETS, list) else []
    except Exception:
        lst = []
    if lst:
        secret = lst[0]
    return jwt.encode(payload, secret, algorithm="HS256")


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
    payload = None
    try:
        jwks_url = os.getenv("JWT_JWKS_URL")
        if jwks_url:
            from superapp_shared.jwks_verify import decode_with_jwks
            aud = os.getenv("JWT_AUDIENCE") if os.getenv("JWT_VALIDATE_AUD", "false").lower() == "true" else None
            iss = os.getenv("JWT_ISSUER") if os.getenv("JWT_VALIDATE_ISS", "false").lower() == "true" else None
            payload = decode_with_jwks(token, jwks_url, audience=aud, issuer=iss)
        else:
            # Try verify against all configured HS256 secrets (rotation)
            last_err = None
            for sec in (settings.JWT_SECRETS if isinstance(settings.JWT_SECRETS, list) else [settings.JWT_SECRET]):
                try:
                    payload = jwt.decode(token, sec, algorithms=["HS256"])
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    payload = None
            if payload is None and last_err is not None:
                raise last_err
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        # Fallback: allow alternate HS256 secrets in dev (e.g., Payments JWT)
        alt = os.getenv("ALT_JWT_SECRETS") or os.getenv("PAYMENTS_JWT_SECRET") or ""
        for sec in [s.strip() for s in alt.split(",") if s.strip()]:
            try:
                payload = jwt.decode(token, sec, algorithms=["HS256"])
                break
            except Exception:
                payload = None
        if payload is None:
            # Dev-only: last resort decode without signature to extract phone
            if os.getenv("ENV", "dev").lower() == "dev":
                try:
                    payload = jwt.decode(token, options={"verify_signature": False})
                except Exception:
                    payload = None
            if payload is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = (payload or {}).get("sub")
    phone = (payload or {}).get("phone")
    if not user_id and not phone:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = db.get(User, user_id) if user_id else None
    if not user and phone:
        # Map by phone (single-login). Create on first sight.
        user = db.query(User).filter(User.phone == phone).one_or_none()
        if user is None:
            user = User(phone=phone, name=None, role="rider")
            db.add(user)
            db.flush()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
