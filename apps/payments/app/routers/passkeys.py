from __future__ import annotations

import base64
import os
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_db, get_current_user, create_access_token
from ..config import settings
from ..models import User, PasskeyCredential

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None  # type: ignore


router = APIRouter(prefix="/auth/passkey", tags=["auth-passkey"])


def _redis_client():
    url = os.getenv("REDIS_URL", "")
    if not url or redis is None:
        return None
    try:
        return redis.from_url(url)
    except Exception:
        return None


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _gen_challenge() -> str:
    return _b64url(secrets.token_bytes(32))


@router.post("/register_challenge")
def register_challenge(user: User = Depends(get_current_user)):
    if not settings.PASSKEYS_ENABLED:
        raise HTTPException(status_code=404, detail="Passkeys disabled")
    challenge = _gen_challenge()
    # Store challenge in Redis (5 min)
    r = _redis_client()
    if r is not None:
        try:
            r.setex(f"pk:reg:{user.id}", 300, challenge)
        except Exception:
            pass
    return {
        "rpId": settings.PASSKEYS_RP_ID,
        "rpName": settings.PASSKEYS_RP_NAME,
        "challenge": challenge,
        "user": {"id": str(user.id), "name": user.phone or (user.name or "")},
    }


@router.post("/register_verify")
def register_verify(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not settings.PASSKEYS_ENABLED:
        raise HTTPException(status_code=404, detail="Passkeys disabled")
    # DEV‑only scaffold: accept without attestation verification when enabled
    if not settings.PASSKEYS_DEV_UNSAFE:
        raise HTTPException(status_code=501, detail="Passkey attestation verification not enabled")
    cred_id = (payload or {}).get("credentialId") or (payload or {}).get("id")
    pub_key = (payload or {}).get("publicKey")
    sign_count = int((payload or {}).get("signCount") or 0)
    if not isinstance(cred_id, str) or len(cred_id) < 8:
        raise HTTPException(status_code=400, detail="Invalid credentialId")
    exists = db.query(PasskeyCredential).filter(PasskeyCredential.credential_id == cred_id).one_or_none()
    if exists is None:
        db.add(PasskeyCredential(user_id=user.id, credential_id=cred_id, public_key=pub_key, sign_count=sign_count, created_at=datetime.utcnow()))
        db.flush()
    return {"detail": "registered"}


@router.post("/login_challenge")
def login_challenge(user: Optional[User] = Depends(get_current_user)):
    # For non‑authenticated clients, allow providing phone as hint (optional)
    # Here we rely on JWT session; in client flows, call this after OTP signup to bind passkey.
    if not settings.PASSKEYS_ENABLED:
        raise HTTPException(status_code=404, detail="Passkeys disabled")
    challenge = _gen_challenge()
    r = _redis_client()
    key = f"pk:auth:{str(user.id) if user else 'anon'}"
    if r is not None:
        try:
            r.setex(key, 300, challenge)
        except Exception:
            pass
    return {"challenge": challenge, "rpId": settings.PASSKEYS_RP_ID}


@router.post("/login_verify")
def login_verify(payload: dict, db: Session = Depends(get_db)):
    if not settings.PASSKEYS_ENABLED:
        raise HTTPException(status_code=404, detail="Passkeys disabled")
    if not settings.PASSKEYS_DEV_UNSAFE:
        raise HTTPException(status_code=501, detail="Passkey assertion verification not enabled")
    cred_id = (payload or {}).get("credentialId") or (payload or {}).get("id")
    if not isinstance(cred_id, str) or len(cred_id) < 8:
        raise HTTPException(status_code=400, detail="Invalid credentialId")
    cred = db.query(PasskeyCredential).filter(PasskeyCredential.credential_id == cred_id).one_or_none()
    if cred is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    user = db.get(User, cred.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    token = create_access_token(str(user.id), user.phone or "")
    return {"access_token": token, "token_type": "bearer"}

