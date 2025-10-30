from fastapi import APIRouter, Depends, Header, HTTPException, status, Request
from sqlalchemy.orm import Session

from ..config import settings
from ..auth import get_db, ensure_user_and_wallet
from ..models import User, PaymentRequest, Invoice, Wallet, Transfer, LedgerEntry
from ..schemas import RequestOut, TransferOut
from ..utils.hmacsig import verify_hmac_and_prevent_replay
from datetime import datetime, timedelta


router = APIRouter(prefix="/internal", tags=["internal"])


def _valid_phone(p: str) -> bool:
    if not p or not isinstance(p, str) or not p.startswith("+"):
        return False
    digits = p[1:]
    return digits.isdigit() and len(digits) >= 7


@router.post("/requests")
def create_payment_request_internal(
    payload: dict,
    db: Session = Depends(get_db),
    secret: str | None = Header(default=None, alias="X-Internal-Secret"),
    sign: str | None = Header(default=None, alias="X-Internal-Sign"),
    ts: str | None = Header(default=None, alias="X-Internal-Ts"),
    idem: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    # Authorize either by strict HMAC or (if allowed) simple shared secret
    authorized = False
    if settings.INTERNAL_API_SECRET:
        if sign and ts:
            # Allow replays when an idempotency key is provided, so callers can safely retry
            authorized = verify_hmac_and_prevent_replay(ts, payload, sign, ttl_override=(0 if idem else None))
        elif not settings.INTERNAL_REQUIRE_HMAC and secret == settings.INTERNAL_API_SECRET:
            authorized = True
    if not authorized:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    from_phone = payload.get("from_phone")
    to_phone = payload.get("to_phone")
    amount_cents = payload.get("amount_cents")
    if not _valid_phone(from_phone) or not _valid_phone(to_phone) or not isinstance(amount_cents, int) or amount_cents <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    if idem and len(idem) > 64:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency key too long")

    requester = ensure_user_and_wallet(db, from_phone, None)
    target = db.query(User).filter(User.phone == to_phone).one_or_none()
    if target is None:
        target = ensure_user_and_wallet(db, to_phone, None)

    # Idempotency support
    if idem:
        existing = db.query(PaymentRequest).filter(PaymentRequest.idempotency_key == idem).one_or_none()
        if existing is not None:
            return {"id": str(existing.id)}

    # Optional expiry support
    exp = None
    exp_in = payload.get("expires_in_minutes")
    if isinstance(exp_in, int) and exp_in > 0:
        # cap at 7 days
        exp = datetime.utcnow() + timedelta(minutes=min(exp_in, 7 * 24 * 60))
    elif settings.REQUEST_EXPIRY_MINUTES:
        exp = datetime.utcnow() + timedelta(minutes=settings.REQUEST_EXPIRY_MINUTES)

    pr = PaymentRequest(
        requester_user_id=requester.id,
        target_user_id=target.id,
        amount_cents=amount_cents,
        currency_code=settings.DEFAULT_CURRENCY,
        status="pending",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        idempotency_key=idem,
        expires_at=exp,
        metadata_json=payload.get("metadata"),
    )
    db.add(pr)
    db.flush()
    return {"id": str(pr.id)}


@router.post("/transfer", response_model=TransferOut)
def internal_transfer(
    payload: dict,
    db: Session = Depends(get_db),
    secret: str | None = Header(default=None, alias="X-Internal-Secret"),
    sign: str | None = Header(default=None, alias="X-Internal-Sign"),
    ts: str | None = Header(default=None, alias="X-Internal-Ts"),
    idem: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    """Direct wallet-to-wallet transfer (server-to-server).
    Auth: internal shared secret or HMAC. Idempotency via X-Idempotency-Key on transfers.
    Body: {"from_phone":"+963...", "to_phone":"+963...", "amount_cents":12345}
    """
    # Authorize either by HMAC or (if allowed) simple shared secret
    authorized = False
    if settings.INTERNAL_API_SECRET:
        if sign and ts:
            # Allow replays when idempotency key provided
            authorized = verify_hmac_and_prevent_replay(ts, payload, sign, ttl_override=(0 if idem else None))
        elif not settings.INTERNAL_REQUIRE_HMAC and secret == settings.INTERNAL_API_SECRET:
            authorized = True
    if not authorized:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    from_phone = payload.get("from_phone")
    to_phone = payload.get("to_phone")
    amount_cents = payload.get("amount_cents")
    if not _valid_phone(from_phone) or not _valid_phone(to_phone) or not isinstance(amount_cents, int) or amount_cents <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    if idem and len(idem) > 64:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency key too long")

    # Idempotency: if key provided and transfer exists, return it
    if idem:
        existing = db.query(Transfer).filter(Transfer.idempotency_key == idem).one_or_none()
        if existing is not None:
            return TransferOut(
                transfer_id=str(existing.id),
                from_wallet_id=str(existing.from_wallet_id) if existing.from_wallet_id else None,
                to_wallet_id=str(existing.to_wallet_id),
                amount_cents=existing.amount_cents,
                currency_code=existing.currency_code,
                status=existing.status,
            )

    # Ensure users and wallets
    from_user = ensure_user_and_wallet(db, from_phone, None)
    to_user = ensure_user_and_wallet(db, to_phone, None)
    from_wallet = db.query(Wallet).filter(Wallet.user_id == from_user.id).with_for_update().one()
    to_wallet = db.query(Wallet).filter(Wallet.user_id == to_user.id).with_for_update().one()
    if from_wallet.currency_code != to_wallet.currency_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Currency mismatch")
    if from_wallet.balance_cents < amount_cents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient balance")

    t = Transfer(
        from_wallet_id=from_wallet.id,
        to_wallet_id=to_wallet.id,
        amount_cents=amount_cents,
        currency_code=from_wallet.currency_code,
        status="completed",
        idempotency_key=idem,
    )
    db.add(t)
    db.flush()

    db.add_all([
        LedgerEntry(transfer_id=t.id, wallet_id=from_wallet.id, amount_cents_signed=-amount_cents),
        LedgerEntry(transfer_id=t.id, wallet_id=to_wallet.id, amount_cents_signed=amount_cents),
    ])
    from_wallet.balance_cents -= amount_cents
    to_wallet.balance_cents += amount_cents
    db.flush()

    return TransferOut(
        transfer_id=str(t.id),
        from_wallet_id=str(from_wallet.id),
        to_wallet_id=str(to_wallet.id),
        amount_cents=amount_cents,
        currency_code=from_wallet.currency_code,
        status=t.status,
    )


@router.get("/wallet")
def internal_get_wallet(
    phone: str,
    db: Session = Depends(get_db),
    secret: str | None = Header(default=None, alias="X-Internal-Secret"),
    sign: str | None = Header(default=None, alias="X-Internal-Sign"),
    ts: str | None = Header(default=None, alias="X-Internal-Ts"),
):
    """Fetch wallet by phone for internal server-to-server checks.
    Auth: internal shared secret or HMAC.
    Response: { phone, wallet_id, balance_cents, currency_code }
    """
    # Authorize either by strict HMAC or (if allowed) simple shared secret
    authorized = False
    if settings.INTERNAL_API_SECRET:
        if sign and ts:
            authorized = verify_hmac_and_prevent_replay(ts, {"phone": phone}, sign)
        elif not settings.INTERNAL_REQUIRE_HMAC and secret == settings.INTERNAL_API_SECRET:
            authorized = True
    if not authorized:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    user = ensure_user_and_wallet(db, phone, None)
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).one()
    return {
        "phone": user.phone,
        "wallet_id": str(wallet.id),
        "balance_cents": wallet.balance_cents,
        "currency_code": wallet.currency_code,
    }


@router.get("/requests/{request_id}")
def internal_get_request(request_id: str, db: Session = Depends(get_db), secret: str | None = Header(default=None, alias="X-Internal-Secret"), sign: str | None = Header(default=None, alias="X-Internal-Sign"), ts: str | None = Header(default=None, alias="X-Internal-Ts")):
    # Authorize via internal secret or HMAC
    authorized = False
    if settings.INTERNAL_API_SECRET:
        if sign and ts:
            authorized = verify_hmac_and_prevent_replay(ts, {"id": request_id}, sign)
        elif not settings.INTERNAL_REQUIRE_HMAC and secret == settings.INTERNAL_API_SECRET:
            authorized = True
    if not authorized:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    pr = db.get(PaymentRequest, request_id)
    if pr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    requester = db.get(User, pr.requester_user_id)
    target = db.get(User, pr.target_user_id)
    return {
        "id": str(pr.id),
        "status": pr.status,
        "amount_cents": pr.amount_cents,
        "requester_phone": requester.phone if requester else None,
        "target_phone": target.phone if target else None,
        "created_at": pr.created_at.isoformat() + "Z",
    }


@router.post("/invoices")
def create_invoice_internal(
    payload: dict,
    db: Session = Depends(get_db),
    secret: str | None = Header(default=None, alias="X-Internal-Secret"),
    sign: str | None = Header(default=None, alias="X-Internal-Sign"),
    ts: str | None = Header(default=None, alias="X-Internal-Ts"),
    idem: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    # Authorize either by strict HMAC or (if allowed) simple shared secret
    authorized = False
    if settings.INTERNAL_API_SECRET:
        if sign and ts:
            # For invoice creation, also allow replay when idempotency key present
            authorized = verify_hmac_and_prevent_replay(ts, payload, sign, ttl_override=(0 if idem else None))
        elif not settings.INTERNAL_REQUIRE_HMAC and secret == settings.INTERNAL_API_SECRET:
            authorized = True
    if not authorized:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    issuer_phone = payload.get("from_phone")
    payer_phone = payload.get("to_phone")
    amount_cents = payload.get("amount_cents")
    due_in_days = payload.get("due_in_days", 0)
    reference = payload.get("reference")
    description = payload.get("description")
    if not _valid_phone(issuer_phone) or not _valid_phone(payer_phone) or not isinstance(amount_cents, int) or amount_cents <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")

    issuer = ensure_user_and_wallet(db, issuer_phone, None)
    payer = ensure_user_and_wallet(db, payer_phone, None)

    if idem:
        # No unique constraint, but honor idempotency manually
        existing = db.query(Invoice).filter(
            Invoice.issuer_user_id == issuer.id,
            Invoice.payer_user_id == payer.id,
            Invoice.amount_cents == amount_cents,
            Invoice.reference == reference,
        ).order_by(Invoice.created_at.desc()).first()
        if existing is not None:
            return {"id": str(existing.id)}

    due_at = datetime.utcnow() + timedelta(days=max(0, int(due_in_days)))
    inv = Invoice(
        issuer_user_id=issuer.id,
        payer_user_id=payer.id,
        amount_cents=amount_cents,
        currency_code=settings.DEFAULT_CURRENCY,
        status="pending",
        reference=reference,
        description=description,
        due_at=due_at,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(inv)
    db.flush()
    return {"id": str(inv.id)}
