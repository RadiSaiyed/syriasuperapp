import secrets

from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.orm import Session

from pydantic import BaseModel, Field
from passlib.context import CryptContext
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
DISABLE_OTP = settings.DEV_MODE and getattr(settings, "DEV_DISABLE_OTP", False)


@router.post("/request_otp", include_in_schema=not DISABLE_OTP)
def request_otp(payload: RequestOtpIn, request: Request):
    if DISABLE_OTP:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
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


@router.post("/verify_otp", response_model=TokenOut, include_in_schema=not DISABLE_OTP)
def verify_otp(payload: VerifyOtpIn, request: Request, db: Session = Depends(get_db)):
    if DISABLE_OTP:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
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
        # Service-specific
        "merchant": {"password": "merchant", "phone": "+963901700101", "name": "Dev Merchant", "is_merchant": True},
        "agent": {"password": "agent", "phone": "+963901700201", "name": "Dev Agent", "is_agent": True},
    }
    u = users.get(payload.username.lower())
    if not u or payload.password != u["password"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    usr = ensure_user_and_wallet(db, phone=u["phone"], name=u.get("name"))
    if u.get("is_merchant") and not usr.is_merchant:
        usr.is_merchant = True
        usr.merchant_status = "approved"
    if u.get("is_agent") and not usr.is_agent:
        usr.is_agent = True
    token = create_access_token(str(usr.id), usr.phone)
    return TokenOut(access_token=token)


# --- Username/Password Registration & Login (production) ---

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    phone: str
    name: str | None = None


@router.post("/register", response_model=TokenOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    """Create a new user with username + password (and required phone).
    Returns an access token on success.
    """
    from ..models import User
    # Enforce unique username and phone
    if db.query(User).filter(User.username == payload.username).one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="username_taken")
    norm_phone = normalize_phone_e164(payload.phone)
    if not norm_phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_phone")
    if db.query(User).filter(User.phone == norm_phone).one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="phone_taken")
    # Hash password
    try:
        ph = pwd_context.hash(payload.password)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="weak_password")
    # Create user + wallet
    user = ensure_user_and_wallet(db, phone=norm_phone, name=payload.name)
    user.username = payload.username
    user.password_hash = ph
    db.flush()
    token = create_access_token(str(user.id), user.phone)
    return TokenOut(access_token=token)


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    from ..models import User
    user = db.query(User).filter(User.username == payload.username).one_or_none()
    if not user or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    if not pwd_context.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    # Ensure wallet exists (legacy rows)
    ensure_user_and_wallet(db, phone=user.phone, name=user.name)
    token = create_access_token(str(user.id), user.phone)
    return TokenOut(access_token=token)
