import os
import jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal


bearer_scheme = HTTPBearer(auto_error=True)


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


def _decode_token(token: str) -> dict:
    jwks_url = os.getenv("JWT_JWKS_URL")
    if jwks_url:
        from superapp_shared.jwks_verify import decode_with_jwks
        aud = os.getenv("JWT_AUDIENCE") if os.getenv("JWT_VALIDATE_AUD", "false").lower() == "true" else None
        iss = os.getenv("JWT_ISSUER") if os.getenv("JWT_VALIDATE_ISS", "false").lower() == "true" else None
        return decode_with_jwks(token, jwks_url, audience=aud, issuer=iss)
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    token = creds.credentials
    try:
        payload = _decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    phone = payload.get("phone")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return type("U", (), {"id": user_id, "phone": phone})
