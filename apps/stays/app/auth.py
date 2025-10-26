import os
import datetime as dt
import jwt
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
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
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


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
    # Cast to UUID object for SQLite compatibility with UUID columns
    try:
        from uuid import UUID as _UUID
        user = db.get(User, _UUID(user_id))
    except Exception:
        user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def try_get_user(request: Request, db: Session) -> User | None:
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            return None
        try:
            from uuid import UUID as _UUID
            return db.get(User, _UUID(user_id))
        except Exception:
            return db.get(User, user_id)
    except Exception:
        return None
