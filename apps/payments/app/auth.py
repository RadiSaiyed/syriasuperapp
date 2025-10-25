import datetime as dt
import jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from .models import User, Wallet, Transfer, LedgerEntry, Merchant, QRCode
from .utils.jwks import get_private_key_pem
from .utils.audit import record_event


bearer_scheme = HTTPBearer(auto_error=True)


def create_access_token(user_id: str, phone: str) -> str:
    now = dt.datetime.utcnow()
    payload = {
        "sub": user_id,
        "phone": phone,
        "iat": int(now.timestamp()),
        "exp": int((now + settings.jwt_expires_delta).timestamp()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    alg = settings.JWT_ALG.upper()
    if alg == 'RS256':
        priv = get_private_key_pem()
        if not priv:
            raise RuntimeError('RS256 enabled but no private key available')
        headers = {"kid": settings.JWT_KEY_ID}
        return jwt.encode(payload, priv, algorithm="RS256", headers=headers)
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
        options = {"require": ["exp", "iat", "sub"], "verify_aud": settings.JWT_VALIDATE_AUD}
        if settings.JWT_ALG.upper() == 'RS256':
            # Payments self-validates RS256 using its own private key's public half
            from cryptography.hazmat.primitives import serialization
            from .utils.jwks import _rsa_public_pem as PUB  # type: ignore
            if PUB is None:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="JWKS not ready")
            public_key = serialization.load_pem_public_key(PUB)
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=(settings.JWT_AUDIENCE if settings.JWT_VALIDATE_AUD else None),
                leeway=settings.JWT_CLOCK_SKEW_SECS,
                options=options,
                issuer=(settings.JWT_ISSUER if settings.JWT_VALIDATE_ISS else None),
            )
        else:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=["HS256"],
                audience=(settings.JWT_AUDIENCE if settings.JWT_VALIDATE_AUD else None),
                leeway=settings.JWT_CLOCK_SKEW_SECS,
                options=options,
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Optional issuer validation
    if settings.JWT_VALIDATE_ISS and payload.get("iss") != settings.JWT_ISSUER:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token issuer")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def ensure_user_and_wallet(db: Session, phone: str, name: str | None):
    user = db.query(User).filter(User.phone == phone).one_or_none()
    if user is None:
        user = User(phone=phone, name=name or None, is_merchant=False)
        db.add(user)
        db.flush()
        wallet = Wallet(user_id=user.id)
        db.add(wallet)
        db.flush()
        # Apply starting credit (idempotent per user via idempotency_key)
        try:
            amt = int(settings.STARTING_CREDIT_CENTS)
        except Exception:
            amt = 0
        if amt and amt > 0:
            t = Transfer(
                from_wallet_id=None,
                to_wallet_id=wallet.id,
                amount_cents=amt,
                currency_code=wallet.currency_code,
                status="completed",
                idempotency_key=f"airdrop:{user.id}",
            )
            db.add(t)
            db.flush()
            db.add(LedgerEntry(transfer_id=t.id, wallet_id=wallet.id, amount_cents_signed=amt))
            wallet.balance_cents = wallet.balance_cents + amt
            db.flush()
            try:
                record_event(db, "wallet.airdrop", str(user.id), {"amount_cents": amt})
            except Exception:
                pass
    else:
        if settings.ENV == "dev" and settings.DEV_RESET_USER_STATE_ON_LOGIN:
            user.kyc_level = 0
            user.kyc_status = "none"
            user.is_merchant = False
            user.merchant_status = "none"
            wallet = db.query(Wallet).filter(Wallet.user_id == user.id).one_or_none()
            merchant = db.query(Merchant).filter(Merchant.user_id == user.id).one_or_none()
            if merchant is not None:
                db.query(QRCode).filter(QRCode.merchant_id == merchant.id).delete(synchronize_session=False)
                db.delete(merchant)
            db.flush()
    return user
