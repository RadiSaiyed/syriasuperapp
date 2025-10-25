import secrets

from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.orm import Session

from pydantic import BaseModel
from superapp_shared import (
    normalize_phone_e164,
    build_client_fingerprint,
    OTPRateLimitError,
    OTPLockoutError,
)
from ..schemas import RequestOtpIn, VerifyOtpIn, TokenOut
from ..auth import create_access_token, ensure_user_and_wallet, get_db
from ..config import settings
from ..utils.otp import send_and_store_otp, verify_otp_code, consume_otp


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/request_otp")
def request_otp(payload: RequestOtpIn, request: Request):
    if not payload.phone or not payload.phone.startswith("+"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone")
    fingerprint = build_client_fingerprint(
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
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
    # Do not expose OTP; return dev hint only in explicit dev mode.
    if settings.OTP_MODE == "dev":
        response["dev_code"] = result.code
    return response


@router.post("/verify_otp", response_model=TokenOut)
def verify_otp(payload: VerifyOtpIn, request: Request, db: Session = Depends(get_db)):
    # Backdoor: allow a specific phone+OTP pair when configured via env
    backdoor_ok = False
    if settings.DEV_MODE and settings.BACKDOOR_PHONE and settings.BACKDOOR_OTP:
        if normalize_phone_e164(payload.phone) == normalize_phone_e164(settings.BACKDOOR_PHONE):
            if secrets.compare_digest(payload.otp.strip(), settings.BACKDOOR_OTP):
                backdoor_ok = True

    fingerprint = build_client_fingerprint(
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )

    if not backdoor_ok and settings.OTP_MODE == "redis" and not payload.session_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing OTP session")

    if backdoor_ok:
        ok = True
    else:
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
    # consume OTP if using redis (skip on backdoor)
    if not backdoor_ok:
        consume_otp(payload.phone, session_id=payload.session_id, client_id=fingerprint)
    user = ensure_user_and_wallet(db, phone=payload.phone, name=payload.name)
    token = create_access_token(str(user.id), user.phone)
    return TokenOut(access_token=token)


class DevLoginIn(BaseModel):
    username: str
    password: str


@router.post("/dev_login", response_model=TokenOut)
def dev_login(payload: DevLoginIn, db: Session = Depends(get_db)):
    """Development-only username/password login that maps to test users.
    Creates users and wallets on first login.
    """
    # Disable in non-dev environments
    if settings.ENV.lower() != "dev":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    users = {
        "admin": {"password": "admin", "phone": "+963901000001", "name": "Admin"},
        "superuser": {"password": "super", "phone": "+963901000002", "name": "Super User"},
        "user1": {"password": "user", "phone": "+963996428955", "name": "SuperAdmin One"},
        "user2": {"password": "user", "phone": "+963996428996", "name": "SuperAdmin Two"},
    }
    u = users.get(payload.username.lower())
    if not u or payload.password != u["password"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    usr = ensure_user_and_wallet(db, phone=u["phone"], name=u.get("name"))
    token = create_access_token(str(usr.id), usr.phone)
    return TokenOut(access_token=token)
