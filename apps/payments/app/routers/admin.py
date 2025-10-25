from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel, Field
import os
import hashlib
import secrets

from ..config import settings
from ..auth import get_db, create_access_token, ensure_user_and_wallet
from ..models import WebhookEndpoint, Transfer, Wallet, Refund, LedgerEntry, User, Merchant
from ..utils.audit import record_event


router = APIRouter(prefix="/admin", tags=["admin"]) 


def require_admin(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
    incoming = x_admin_token or ""
    # Allow plain token match if provided
    token_plain = os.getenv("ADMIN_TOKEN", getattr(settings, "ADMIN_TOKEN", ""))
    for candidate in [t.strip() for t in token_plain.split(',') if t.strip()]:
        if secrets.compare_digest(incoming, candidate):
            return
    # Else check hashed list (comma-separated SHA-256 hex digests)
    try:
        digest = hashlib.sha256(incoming.encode()).hexdigest().lower()
    except Exception:
        digest = ""
    for h in getattr(settings, "admin_token_hashes", []) or []:
        if secrets.compare_digest(digest, (h or "").strip().lower()):
            return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin token invalid")


class FeesIn(BaseModel):
    merchant_fee_bps: int | None = None
    cashin_fee_bps: int | None = None
    cashout_fee_bps: int | None = None
    fee_wallet_phone: str | None = None


@router.get("/config/fees")
def get_fees(_: None = Depends(require_admin)):
    return {
        "merchant_fee_bps": settings.MERCHANT_FEE_BPS,
        "cashin_fee_bps": settings.CASHIN_FEE_BPS,
        "cashout_fee_bps": settings.CASHOUT_FEE_BPS,
        "fee_wallet_phone": settings.FEE_WALLET_PHONE,
    }


@router.post("/config/fees")
def set_fees(payload: FeesIn, _: None = Depends(require_admin)):
    if payload.merchant_fee_bps is not None:
        settings.MERCHANT_FEE_BPS = int(payload.merchant_fee_bps)
    if payload.cashin_fee_bps is not None:
        settings.CASHIN_FEE_BPS = int(payload.cashin_fee_bps)
    if payload.cashout_fee_bps is not None:
        settings.CASHOUT_FEE_BPS = int(payload.cashout_fee_bps)
    if payload.fee_wallet_phone is not None and payload.fee_wallet_phone.strip():
        settings.FEE_WALLET_PHONE = payload.fee_wallet_phone.strip()
    return get_fees()


class RateLimitIn(BaseModel):
    per_minute: int | None = None
    auth_boost: int | None = None
    exempt_otp: bool | None = None


@router.post("/config/rate_limit")
def set_rate_limit(payload: RateLimitIn, _: None = Depends(require_admin)):
    if payload.per_minute is not None:
        os.environ["RL_LIMIT_PER_MINUTE_OVERRIDE"] = str(int(payload.per_minute))
    if payload.auth_boost is not None:
        os.environ["RL_AUTH_BOOST_OVERRIDE"] = str(int(payload.auth_boost))
    if payload.exempt_otp is not None:
        os.environ["RL_EXEMPT_OTP"] = "true" if payload.exempt_otp else "false"
    return {
        "per_minute": int(os.getenv("RL_LIMIT_PER_MINUTE_OVERRIDE", "0") or 0),
        "auth_boost": int(os.getenv("RL_AUTH_BOOST_OVERRIDE", "0") or 0),
        "exempt_otp": os.getenv("RL_EXEMPT_OTP", "true"),
    }


class ToggleIn(BaseModel):
    active: bool


@router.post("/webhooks/endpoints/{endpoint_id}/toggle")
def toggle_webhook(endpoint_id: str, payload: ToggleIn, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    ep = db.get(WebhookEndpoint, endpoint_id)
    if not ep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    ep.active = bool(payload.active)
    db.flush()
    return {"id": endpoint_id, "active": ep.active}


@router.get("/webhooks/endpoints")
def list_webhook_endpoints(db: Session = Depends(get_db), _: None = Depends(require_admin)):
    rows = db.query(WebhookEndpoint).order_by(WebhookEndpoint.created_at.desc()).limit(200).all()
    out = []
    for e in rows:
        u = db.get(User, e.user_id)
        out.append({
            "id": str(e.id),
            "user_id": str(e.user_id),
            "user_phone": u.phone if u else None,
            "url": e.url,
            "active": e.active,
            "created_at": e.created_at.isoformat() + "Z",
        })
    return out


class RefundAdminIn(BaseModel):
    original_transfer_id: str
    amount_cents: int


@router.post("/refunds")
def admin_create_refund(payload: RefundAdminIn, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    if payload.amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")
    t0 = db.get(Transfer, payload.original_transfer_id)
    if not t0:
        raise HTTPException(status_code=404, detail="Original transfer not found")
    mw = db.get(Wallet, t0.to_wallet_id)
    pw = db.get(Wallet, t0.from_wallet_id) if t0.from_wallet_id else None
    if not mw or not pw:
        raise HTTPException(status_code=400, detail="Invalid original transfer")
    mw = db.execute(select(Wallet).where(Wallet.id == mw.id).with_for_update()).scalar_one()
    pw = db.execute(select(Wallet).where(Wallet.id == pw.id).with_for_update()).scalar_one()
    if mw.balance_cents < payload.amount_cents:
        raise HTTPException(status_code=400, detail="Insufficient merchant balance")
    t = Transfer(from_wallet_id=mw.id, to_wallet_id=pw.id, amount_cents=payload.amount_cents, currency_code=mw.currency_code, status="completed")
    db.add(t); db.flush()
    db.add_all([
        LedgerEntry(transfer_id=t.id, wallet_id=mw.id, amount_cents_signed=-payload.amount_cents),
        LedgerEntry(transfer_id=t.id, wallet_id=pw.id, amount_cents_signed=payload.amount_cents),
    ])
    mw.balance_cents -= payload.amount_cents
    pw.balance_cents += payload.amount_cents
    r = Refund(original_transfer_id=t0.id, amount_cents=payload.amount_cents, currency_code=mw.currency_code, status="completed")
    db.add(r); db.flush()
    return {"transfer_id": str(t.id), "refund_id": str(r.id)}


@router.get("/merchants")
def get_merchant(phone: str | None = None, limit: int = 50, offset: int = 0, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    limit = max(1, min(200, limit))
    offset = max(0, offset)
    if phone:
        u = db.query(User).filter(User.phone == phone).one_or_none()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        m = db.query(Merchant).filter(Merchant.user_id == u.id).one_or_none()
        return {
            "user_id": str(u.id),
            "phone": u.phone,
            "is_merchant": u.is_merchant,
            "merchant_status": u.merchant_status,
            "merchant_fee_bps": (m.fee_bps if m else None),
        }
    # else: list first 50 merchants
    users = (
        db.query(User)
        .filter(User.is_merchant == True)  # noqa: E712
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    out = []
    for u in users:
        m = db.query(Merchant).filter(Merchant.user_id == u.id).one_or_none()
        out.append({
            "user_id": str(u.id), "phone": u.phone, "is_merchant": u.is_merchant, "merchant_status": u.merchant_status, "merchant_fee_bps": (m.fee_bps if m else None)
        })
    return {"items": out, "limit": limit, "offset": offset}


class MerchantSetIn(BaseModel):
    is_merchant: bool | None = None
    merchant_status: str | None = None
    merchant_fee_bps: int | None = None


@router.post("/merchants/{user_id}/set")
def set_merchant(user_id: str, payload: MerchantSetIn, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.is_merchant is not None:
        u.is_merchant = bool(payload.is_merchant)
    if payload.merchant_status is not None and payload.merchant_status.strip():
        u.merchant_status = payload.merchant_status.strip()
    if payload.merchant_fee_bps is not None:
        m = db.query(Merchant).filter(Merchant.user_id == u.id).one_or_none()
        if not m and u.is_merchant:
            # Auto-provision merchant bound to user's wallet
            w = db.query(Wallet).filter(Wallet.user_id == u.id).one_or_none()
            if not w:
                w = Wallet(user_id=u.id)
                db.add(w); db.flush()
            m = Merchant(user_id=u.id, wallet_id=w.id)
            db.add(m); db.flush()
        if m:
            m.fee_bps = int(payload.merchant_fee_bps)
    db.flush()
    return {"detail": "ok"}


@router.get("/webhooks/endpoints/{endpoint_id}/deliveries")
def list_endpoint_deliveries(endpoint_id: str, limit: int = 50, offset: int = 0, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    limit = max(1, min(200, limit))
    offset = max(0, offset)
    q = (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.endpoint_id == endpoint_id)
        .order_by(WebhookDelivery.created_at.desc())
    )
    rows = q.offset(offset).limit(limit).all()
    return {
        "items": [
            {
                "id": str(d.id),
                "event_type": d.event_type,
                "status": d.status,
                "attempt_count": d.attempt_count,
                "last_error": d.last_error,
                "created_at": d.created_at.isoformat() + "Z",
            }
            for d in rows
        ],
        "limit": limit,
        "offset": offset,
    }


@router.post("/webhooks/deliveries/{delivery_id}/requeue")
def admin_requeue_delivery(delivery_id: str, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    d = db.get(WebhookDelivery, delivery_id)
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    d.status = "pending"
    d.attempt_count = 0
    d.last_error = None
    d.next_attempt_at = None
    db.flush()
    return {"detail": "requeued"}


class AirdropIn(BaseModel):
    amount_cents: int | None = None
    limit: int = 10000
    offset: int = 0


@router.post("/airdrop_starting_credit")
def admin_airdrop_starting_credit(
    payload: AirdropIn,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    Backfill starting credit to existing users who haven't received it yet.
    Idempotent per user via idempotency_key "airdrop:<user_id>".
    """
    amt = int(payload.amount_cents or settings.STARTING_CREDIT_CENTS)
    if amt <= 0:
        return {"processed": 0, "credited": 0, "skipped": 0, "amount_cents": amt}

    limit = max(1, min(50000, int(payload.limit)))
    offset = max(0, int(payload.offset))

    users = (
        db.query(User)
        .order_by(User.created_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    processed = 0
    credited = 0
    skipped = 0
    for u in users:
        processed += 1
        # Ensure wallet exists
        w = db.query(Wallet).filter(Wallet.user_id == u.id).one_or_none()
        if w is None:
            w = Wallet(user_id=u.id)
            db.add(w)
            db.flush()
        # Skip if already airdropped
        idem = f"airdrop:{u.id}"
        existing = db.query(Transfer).filter(Transfer.idempotency_key == idem).one_or_none()
        if existing is not None:
            skipped += 1
            continue
        # Credit
        t = Transfer(
            from_wallet_id=None,
            to_wallet_id=w.id,
            amount_cents=amt,
            currency_code=w.currency_code,
            status="completed",
            idempotency_key=idem,
        )
        db.add(t)
        db.flush()
        db.add(LedgerEntry(transfer_id=t.id, wallet_id=w.id, amount_cents_signed=amt))
        w.balance_cents = w.balance_cents + amt
        credited += 1
        try:
            record_event(db, "wallet.airdrop.admin", str(u.id), {"amount_cents": amt})
        except Exception:
            pass
    db.flush()
    return {"processed": processed, "credited": credited, "skipped": skipped, "amount_cents": amt, "limit": limit, "offset": offset}


class DemoSeedIn(BaseModel):
    phone: str = Field(description="E.164 phone, e.g. +9639…")
    name: str | None = None
    starting_balance_cents: int = Field(default=0, ge=0)
    kyc_level: int | None = Field(default=1, ge=0, le=2)
    kyc_status: str | None = Field(default="approved")
    is_merchant: bool = False
    merchant_fee_bps: int | None = None


@router.post("/seed_demo_user")
def seed_demo_user(
    payload: DemoSeedIn,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    Create or update a demo user for testing. Idempotent on phone.
    - Ensures user + wallet exist
    - Optionally sets KYC and merchant flags
    - Optionally credits starting balance (ledger + wallet update)
    - Returns an access token for immediate use
    """
    # Ensure user + wallet
    user = ensure_user_and_wallet(db, phone=payload.phone.strip(), name=payload.name)
    if payload.name:
        user.name = payload.name.strip()
    # KYC settings
    if payload.kyc_level is not None:
        user.kyc_level = int(payload.kyc_level)
    if payload.kyc_status is not None and payload.kyc_status.strip():
        user.kyc_status = payload.kyc_status.strip()
    # Merchant
    if payload.is_merchant:
        user.is_merchant = True
        user.merchant_status = "approved"
        m = db.query(Merchant).filter(Merchant.user_id == user.id).one_or_none()
        if not m:
            w = db.query(Wallet).filter(Wallet.user_id == user.id).one_or_none()
            if not w:
                w = Wallet(user_id=user.id)
                db.add(w); db.flush()
            m = Merchant(user_id=user.id, wallet_id=w.id)
            db.add(m); db.flush()
        if payload.merchant_fee_bps is not None:
            m.fee_bps = int(payload.merchant_fee_bps)
    # Credit starting balance (idempotent: skip if an idempotency key exists for this user+seed)
    amt = int(payload.starting_balance_cents or 0)
    if amt > 0:
        w = db.query(Wallet).filter(Wallet.user_id == user.id).with_for_update().one()
        idem = f"seed:{user.id}:{amt}"
        exists = db.query(Transfer).filter(Transfer.idempotency_key == idem).one_or_none()
        if exists is None:
            t = Transfer(
                from_wallet_id=None,
                to_wallet_id=w.id,
                amount_cents=amt,
                currency_code=w.currency_code,
                status="completed",
                idempotency_key=idem,
            )
            db.add(t); db.flush()
            db.add(LedgerEntry(transfer_id=t.id, wallet_id=w.id, amount_cents_signed=amt))
            w.balance_cents = w.balance_cents + amt
            try:
                record_event(db, "wallet.seed_demo", str(user.id), {"amount_cents": amt})
            except Exception:
                pass
    db.flush()
    # Return token and basic profile
    token = create_access_token(str(user.id), user.phone)
    w = db.query(Wallet).filter(Wallet.user_id == user.id).one()
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "phone": user.phone,
            "name": user.name,
            "is_merchant": user.is_merchant,
            "kyc_level": user.kyc_level,
            "kyc_status": user.kyc_status,
        },
        "wallet": {
            "id": str(w.id),
            "balance_cents": int(w.balance_cents),
            "currency_code": w.currency_code,
        },
    }
