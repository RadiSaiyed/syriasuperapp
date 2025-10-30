from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.orm import Session

from superapp_shared import build_client_fingerprint, OTPRateLimitError, OTPLockoutError
from ..schemas import RequestOtpIn, VerifyOtpIn, TokenOut
from ..auth import create_access_token, get_db
from ..config import settings
from ..utils.otp import send_and_store_otp, verify_otp_code, consume_otp
from ..models import User
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
        "consumer": {"password": "consumer", "phone": "+963901500101", "name": "Dev Consumer"},
        "agent": {"password": "agent", "phone": "+963901500201", "name": "Dev Agent"},
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
