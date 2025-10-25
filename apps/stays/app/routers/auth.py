from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.orm import Session

from superapp_shared import build_client_fingerprint, OTPRateLimitError, OTPLockoutError
from ..schemas import RequestOtpIn, VerifyOtpIn, TokenOut
from ..auth import create_access_token
from ..database import get_db
from ..models import User
from ..config import settings
from ..utils.otp import send_and_store_otp, verify_otp_code, consume_otp


router = APIRouter(prefix="/auth", tags=["auth"])


def _fingerprint(request: Request) -> str:
    return build_client_fingerprint(
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


@router.post("/request_otp")
def request_otp(payload: RequestOtpIn, request: Request):
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


@router.post("/verify_otp", response_model=TokenOut)
def verify_otp(payload: VerifyOtpIn, request: Request, db: Session = Depends(get_db)):
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
        role = payload.role if payload.role in ("guest", "host") else "guest"
        user = User(phone=payload.phone, name=payload.name or None, role=role)
        db.add(user)
        db.flush()
    token = create_access_token(str(user.id), user.phone)
    return TokenOut(access_token=token)
