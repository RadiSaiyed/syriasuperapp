from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.orm import Session

from superapp_shared import build_client_fingerprint, OTPRateLimitError, OTPLockoutError
from ..schemas import RequestOtpIn, VerifyOtpIn, TokenOut
from ..auth import create_access_token
from .. import auth as auth_mod
from ..database import get_db
from ..models import User
from ..config import settings
from ..utils.otp import send_and_store_otp, verify_otp_code, consume_otp
import os
try:
    import pyotp  # type: ignore
except Exception:
    pyotp = None
from pydantic import BaseModel


router = APIRouter(prefix="/auth", tags=["auth"])
DISABLE_OTP = settings.DEV_MODE and getattr(settings, "DEV_DISABLE_OTP", False)


def _fingerprint(request: Request) -> str:
    return build_client_fingerprint(
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


@router.post("/request_otp", include_in_schema=not DISABLE_OTP)
def request_otp(payload: RequestOtpIn, request: Request):
    if DISABLE_OTP:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    if not payload.phone or not payload.phone.startswith("+"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone")
    fingerprint = _fingerprint(request)
    try:
        result = send_and_store_otp(
            payload.phone,
            device_key=fingerprint,
            client_id=fingerprint,
        )
    except OTPRateLimitError as exc:
        detail = {"code": "otp_rate_limited", "retry_after": exc.retry_after}
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)
    response = {"detail": "OTP sent", "otp_session": result.session_id}
    if settings.OTP_MODE == "dev":
        response["dev_code"] = result.code
    return response


@router.post("/verify_otp", response_model=TokenOut, include_in_schema=not DISABLE_OTP)
def verify_otp(payload: VerifyOtpIn, request: Request, db: Session = Depends(get_db)):
    if DISABLE_OTP:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    if settings.OTP_MODE == "redis" and not payload.session_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing OTP session")

    fingerprint = _fingerprint(request)
    try:
        ok = verify_otp_code(
            payload.phone,
            payload.otp,
            session_id=payload.session_id,
            device_key=fingerprint,
            client_id=fingerprint,
        )
    except OTPLockoutError as exc:
        detail = {"code": "otp_locked", "retry_after": exc.retry_after}
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)

    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")
    consume_otp(payload.phone, session_id=payload.session_id, client_id=fingerprint)
    user = db.query(User).filter(User.phone == payload.phone).one_or_none()
    if user is None:
        user = User(phone=payload.phone, name=payload.name or None)
        db.add(user)
        db.flush()
    # Optional TOTP enforcement
    if getattr(settings, "REQUIRE_TOTP", False):
        code = getattr(payload, "totp", None)
        if not user.totp_secret or not getattr(user, "twofa_enabled", False):
            # Allow login until user enables 2FA
            pass
        else:
            if pyotp is None:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="2FA required but TOTP lib missing")
            totp = pyotp.TOTP(user.totp_secret)
            if not code or not totp.verify(str(code), valid_window=1):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid 2FA code")
    token = create_access_token(str(user.id), user.phone)
    return TokenOut(access_token=token)


class DevLoginIn(BaseModel):
    username: str
    password: str


@router.post("/dev_login", response_model=TokenOut)
def dev_login(payload: DevLoginIn, db: Session = Depends(get_db)):
    if settings.ENV.lower() != "dev":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    users = {
        "admin": {"password": "admin", "phone": "+963901000001", "name": "Admin"},
        "superuser": {"password": "super", "phone": "+963901000002", "name": "Super User"},
        "user1": {"password": "user", "phone": "+963996428955", "name": "User One"},
        "user2": {"password": "user", "phone": "+963996428996", "name": "User Two"},
        # Optional aliases
        "operator": {"password": "operator", "phone": "+963901600101", "name": "Dev Operator"},
        "eater": {"password": "eater", "phone": "+963901600201", "name": "Dev Eater"},
    }
    u = users.get(payload.username.lower())
    if not u or payload.password != u["password"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user = db.query(User).filter(User.phone == u["phone"]).one_or_none()
    if user is None:
        user = User(phone=u["phone"], name=u.get("name"))
        db.add(user)
        db.flush()
    token = create_access_token(str(user.id), user.phone)
    return TokenOut(access_token=token)


@router.post("/totp/setup")
def totp_setup(user: User = Depends(auth_mod.get_current_user), db: Session = Depends(get_db)):
    if pyotp is None:
        raise HTTPException(status_code=500, detail="TOTP unavailable")
    if not user.totp_secret:
        secret = pyotp.random_base32()
        u = db.get(User, user.id); u.totp_secret = secret
    else:
        secret = user.totp_secret
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.phone or "user", issuer_name="Food Operator")
    return {"secret": secret, "otpauth_uri": uri}


@router.post("/totp/enable")
def totp_enable(code: str, user: User = Depends(auth_mod.get_current_user), db: Session = Depends(get_db)):
    if pyotp is None:
        raise HTTPException(status_code=500, detail="TOTP unavailable")
    u = db.get(User, user.id)
    if not u.totp_secret:
        raise HTTPException(status_code=400, detail="No secret")
    if not pyotp.TOTP(u.totp_secret).verify(str(code), valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid 2FA code")
    u.twofa_enabled = True
    return {"detail": "ok"}
