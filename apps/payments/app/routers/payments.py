import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..config import settings
from ..models import Wallet, User, Transfer, LedgerEntry, Merchant, QRCode, PaymentRequest
from ..schemas import QRCreateIn, QROut, QRPayIn, TransferOut
from ..utils.kyc_policy import require_min_kyc_level, enforce_tx_limits
from ..utils.fees import ensure_fee_wallet, calc_fee_bps
from ..utils.audit import record_event
from ..utils.fraud import check_qr_velocity
from ..utils.risk import evaluate_risk_and_maybe_block
from prometheus_client import Counter
from fastapi import Header
from ..utils.idempotency import resolve_idempotency_key
from sqlalchemy.exc import IntegrityError
from ..utils.idempotency_store import reserve as idem_reserve, finalize as idem_finalize

PAY_COUNTER = Counter("payments_qr_total", "QR payments", ["status"]) 
# Merchant revenue KPIs (cents)
REVENUE_GROSS_CENTS = Counter("payments_merchant_gross_cents", "Merchant gross inflows (cents)", ["currency"]) 
REVENUE_FEES_CENTS = Counter("payments_merchant_fees_cents", "Merchant fees charged (cents)", ["currency"]) 


router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/dev/become_merchant")
def dev_become_merchant(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if settings.ENV != "dev":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    if not user.is_merchant:
        user.is_merchant = True
        db.flush()
    merchant = db.query(Merchant).filter(Merchant.user_id == user.id).one_or_none()
    if merchant is None:
        wallet = db.query(Wallet).filter(Wallet.user_id == user.id).one()
        merchant = Merchant(user_id=user.id, wallet_id=wallet.id)
        db.add(merchant)
        db.flush()
    return {"detail": "merchant enabled"}


@router.post("/merchant/apply")
def apply_merchant(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.merchant_status == "approved" and user.is_merchant:
        return {"detail": "already merchant"}
    if user.kyc_status != "approved":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="KYC approval required")
    user.merchant_status = "applied"
    db.flush()
    return {"detail": "application received"}


@router.get("/merchant/status")
def merchant_status(user: User = Depends(get_current_user)):
    return {"is_merchant": user.is_merchant, "merchant_status": user.merchant_status}


@router.get("/merchant/statement")
def merchant_statement(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    from_ts: str | None = None,
    to_ts: str | None = None,
    format: str = "json",
):
    if not user.is_merchant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a merchant")
    merchant = db.query(Merchant).filter(Merchant.user_id == user.id).one_or_none()
    if merchant is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Merchant not provisioned")
    mw = db.query(Wallet).filter(Wallet.id == merchant.wallet_id).one()

    # Parse time range
    from_dt = None
    to_dt = None
    from datetime import datetime, timedelta
    try:
        if from_ts:
            from_dt = datetime.fromisoformat(from_ts.replace("Z", "+00:00")).replace(tzinfo=None)
        if to_ts:
            to_dt = datetime.fromisoformat(to_ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid time range")
    if not to_dt:
        to_dt = datetime.utcnow()
    if not from_dt:
        from_dt = to_dt - timedelta(days=30)

    # Gross income: transfers to merchant wallet
    q_income = db.query(Transfer).filter(
        Transfer.to_wallet_id == mw.id,
        Transfer.created_at >= from_dt,
        Transfer.created_at <= to_dt,
    ).all()
    gross = sum(t.amount_cents for t in q_income)

    # Fees: transfers from merchant to fee wallet
    from ..utils.fees import ensure_fee_wallet
    fee_wallet = ensure_fee_wallet(db)
    q_fees = db.query(Transfer).filter(
        Transfer.from_wallet_id == mw.id,
        Transfer.to_wallet_id == fee_wallet.id,
        Transfer.created_at >= from_dt,
        Transfer.created_at <= to_dt,
    ).all()
    fees = sum(t.amount_cents for t in q_fees)
    net = gross - fees

    rows = [
        {
            "created_at": t.created_at.isoformat() + "Z",
            "direction": "in",
            "amount_cents": t.amount_cents,
            "currency_code": t.currency_code,
            "transfer_id": str(t.id),
        }
        for t in q_income
    ] + [
        {
            "created_at": t.created_at.isoformat() + "Z",
            "direction": "fee",
            "amount_cents": -t.amount_cents,
            "currency_code": t.currency_code,
            "transfer_id": str(t.id),
        }
        for t in q_fees
    ]

    if format.lower() == "csv":
        from fastapi import Response
        import csv
        from io import StringIO
        buf = StringIO()
        w = csv.writer(buf)
        w.writerow(["created_at", "direction", "amount_cents", "currency_code", "transfer_id"])
        for r in rows:
            w.writerow([r["created_at"], r["direction"], r["amount_cents"], r["currency_code"], r["transfer_id"]])
        return Response(buf.getvalue(), media_type="text/csv")

    return {"from": from_dt.isoformat() + "Z", "to": to_dt.isoformat() + "Z", "gross_cents": gross, "fees_cents": fees, "net_cents": net, "rows": rows[:1000]}


@router.post("/merchant/qr", response_model=QROut)
def create_qr(
    payload: QRCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Require minimal KYC level to create QR
    require_min_kyc_level(user, settings.KYC_MIN_LEVEL_FOR_MERCHANT_QR)
    if not user.is_merchant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a merchant")
    merchant = db.query(Merchant).filter(Merchant.user_id == user.id).one_or_none()
    if merchant is None:
        # Auto‑provision merchant record bound to user's wallet
        wallet = db.query(Wallet).filter(Wallet.user_id == user.id).one()
        merchant = Merchant(user_id=user.id, wallet_id=wallet.id)
        db.add(merchant)
        db.flush()

    expires_at = datetime.utcnow() + timedelta(minutes=settings.QR_EXPIRY_MINUTES)
    opaque = secrets.token_urlsafe(24)
    code_str = f"PAY:v1;code={opaque}"

    mode = payload.mode if payload.mode in ("dynamic", "static") else "dynamic"
    qr = QRCode(
        merchant_id=merchant.id,
        code=opaque,
        amount_cents=payload.amount_cents if mode == "dynamic" else 0,
        currency_code=payload.currency_code,
        expires_at=expires_at,
        status="active",
        mode=mode,
    )
    db.add(qr)
    db.flush()

    out = QROut(code=code_str, expires_at=expires_at.isoformat() + "Z")
    record_event(db, "payments.qr_create", str(user.id), {"amount_cents": payload.amount_cents})
    return out


@router.get("/cpm_qr")
def cpm_qr(format: str = "phone", user: User = Depends(get_current_user)):
    """Return a CPM QR text for the current user to display in their app.

    format=phone | id (default phone)
    """
    fmt = (format or "phone").lower()
    if fmt not in ("phone", "id"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid format")
    if fmt == "phone":
        qr = f"CPM:v1;phone={user.phone}"
    else:
        qr = f"CPM:v1;id={user.id}"
    return {"qr_text": qr}


@router.post("/merchant/pay", response_model=TransferOut)
def pay_qr(
    payload: QRPayIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idem_hdr: str | None = Header(default=None, alias="Idempotency-Key"),
):
    # Require minimal KYC level for merchant payments
    require_min_kyc_level(user, settings.KYC_MIN_LEVEL_FOR_MERCHANT_PAY)
    # Velocity guard
    check_qr_velocity(db, user, 1)
    # Idempotency on transfers.idempotency_key (header preferred, fallback to body)
    idem_key = resolve_idempotency_key(idem_hdr, getattr(payload, "idempotency_key", None))
    idem_rec = None
    # Reserve idempotency with synthesized request fingerprint; replay returns prior result
    if idem_key:
        idem_rec, state = idem_reserve(db, str(user.id), "POST", "/payments/merchant/pay", idem_key, payload)
        if state == "replay" and idem_rec.result_ref:
            existing = db.query(Transfer).filter(Transfer.id == idem_rec.result_ref).one_or_none()
            if existing:
                return TransferOut(
                    transfer_id=str(existing.id),
                    from_wallet_id=str(existing.from_wallet_id) if existing.from_wallet_id else None,
                    to_wallet_id=str(existing.to_wallet_id),
                    amount_cents=existing.amount_cents,
                    currency_code=existing.currency_code,
                    status=existing.status,
                )
    existing = db.query(Transfer).filter(Transfer.idempotency_key == idem_key).one_or_none()
    if existing:
        return TransferOut(
            transfer_id=str(existing.id),
            from_wallet_id=str(existing.from_wallet_id) if existing.from_wallet_id else None,
            to_wallet_id=str(existing.to_wallet_id),
            amount_cents=existing.amount_cents,
            currency_code=existing.currency_code,
            status=existing.status,
        )

    prefix = "PAY:v1;code="
    if not payload.code.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR format")
    opaque = payload.code[len(prefix) :]

    qr = db.query(QRCode).filter(QRCode.code == opaque).with_for_update().one_or_none()
    # Re-check idempotency after acquiring the row lock to handle concurrent calls
    existing2 = db.query(Transfer).filter(Transfer.idempotency_key == idem_key).one_or_none()
    if existing2:
        return TransferOut(
            transfer_id=str(existing2.id),
            from_wallet_id=str(existing2.from_wallet_id) if existing2.from_wallet_id else None,
            to_wallet_id=str(existing2.to_wallet_id) if existing2.to_wallet_id else None,
            amount_cents=existing2.amount_cents,
            currency_code=existing2.currency_code,
            status=existing2.status,
        )
    if qr is None or qr.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR not active")
    if qr.expires_at < datetime.utcnow():
        qr.status = "expired"
        db.flush()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="QR expired")

    payer_wallet = db.query(Wallet).filter(Wallet.user_id == user.id).with_for_update().one()
    merchant = db.query(Merchant).filter(Merchant.id == qr.merchant_id).one()
    merchant_wallet = db.query(Wallet).filter(Wallet.id == merchant.wallet_id).with_for_update().one()

    if payer_wallet.currency_code != qr.currency_code or merchant_wallet.currency_code != qr.currency_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Currency mismatch")
    # Choose amount depending on mode
    amount = qr.amount_cents
    if qr.mode == "static":
        if payload.amount_cents is None or payload.amount_cents <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount required for static QR")
        amount = payload.amount_cents
    # KYC limits for payer
    enforce_tx_limits(db, user, amount)
    if payer_wallet.balance_cents < amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient balance")
    # Risk engine (optional)
    try:
        evaluate_risk_and_maybe_block(db, user, amount, context="qr_pay", merchant_user_id=str(merchant_wallet.user_id))
    except HTTPException:
        raise

    try:
        transfer = Transfer(
            from_wallet_id=payer_wallet.id,
            to_wallet_id=merchant_wallet.id,
            amount_cents=amount,
            currency_code=qr.currency_code,
            status="completed",
            idempotency_key=idem_key,
        )
        db.add(transfer)
        db.flush()

        debit = LedgerEntry(transfer_id=transfer.id, wallet_id=payer_wallet.id, amount_cents_signed=-amount)
        credit = LedgerEntry(transfer_id=transfer.id, wallet_id=merchant_wallet.id, amount_cents_signed=amount)
        db.add_all([debit, credit])

        payer_wallet.balance_cents -= amount
        merchant_wallet.balance_cents += amount

        if qr.mode == "dynamic":
            qr.status = "used"
        db.flush()

        # Fees: charge merchant fee after settlement (separate transfer)
        fee_bps = merchant.fee_bps if getattr(merchant, "fee_bps", None) is not None else settings.MERCHANT_FEE_BPS
        fee_amount = calc_fee_bps(amount, fee_bps)
        if fee_amount > 0:
            fee_wallet = ensure_fee_wallet(db)
            # Lock the fee wallet row to avoid lost updates under concurrency
            fee_wallet = (
                db.query(Wallet)
                .filter(Wallet.id == fee_wallet.id)
                .with_for_update()
                .one()
            )
            # Ensure merchant has funds for fee (it just received funds above)
            if merchant_wallet.balance_cents < fee_amount:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Fee settlement failed")
            t_fee = Transfer(
                from_wallet_id=merchant_wallet.id,
                to_wallet_id=fee_wallet.id,
                amount_cents=fee_amount,
                currency_code=qr.currency_code,
                status="completed",
                idempotency_key=None,
            )
            db.add(t_fee)
            db.flush()
            db.add_all(
                [
                    LedgerEntry(transfer_id=t_fee.id, wallet_id=merchant_wallet.id, amount_cents_signed=-fee_amount),
                    LedgerEntry(transfer_id=t_fee.id, wallet_id=fee_wallet.id, amount_cents_signed=fee_amount),
                ]
            )
            merchant_wallet.balance_cents -= fee_amount
            fee_wallet.balance_cents += fee_amount
            db.flush()
            try:
                REVENUE_FEES_CENTS.labels(qr.currency_code).inc(fee_amount)
            except Exception:
                pass

        out = TransferOut(
            transfer_id=str(transfer.id),
            from_wallet_id=str(payer_wallet.id),
            to_wallet_id=str(merchant_wallet.id),
            amount_cents=transfer.amount_cents,
            currency_code=transfer.currency_code,
            status=transfer.status,
        )
        try:
            if idem_rec is not None:
                idem_finalize(db, idem_rec, str(transfer.id))
        except Exception:
            pass
        record_event(db, "payments.qr_pay", str(user.id), {"amount_cents": transfer.amount_cents})
        try:
            PAY_COUNTER.labels("completed").inc()
            REVENUE_GROSS_CENTS.labels(transfer.currency_code).inc(transfer.amount_cents)
        except Exception:
            pass
        return out
    except IntegrityError:
        # Another concurrent request created the same idempotent transfer first.
        # Roll back our partial transaction and return the existing transfer.
        db.rollback()
        existing = db.query(Transfer).filter(Transfer.idempotency_key == idem_key).one_or_none()
        if existing is None:
            # If still not found, propagate error
            raise
        try:
            PAY_COUNTER.labels("completed").inc()
        except Exception:
            pass
        return TransferOut(
            transfer_id=str(existing.id),
            from_wallet_id=str(existing.from_wallet_id) if existing.from_wallet_id else None,
            to_wallet_id=str(existing.to_wallet_id) if existing.to_wallet_id else None,
            amount_cents=existing.amount_cents,
            currency_code=existing.currency_code,
            status=existing.status,
        )


@router.get("/merchant/qr_status")
def qr_status(code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_merchant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a merchant")
    prefix = "PAY:v1;code="
    if not code.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR format")
    opaque = code[len(prefix) :]
    merchant = db.query(Merchant).filter(Merchant.user_id == user.id).one_or_none()
    if merchant is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Merchant not provisioned")
    qr = db.query(QRCode).filter(QRCode.code == opaque, QRCode.merchant_id == merchant.id).one_or_none()
    if qr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR not found")
    return {
        "status": qr.status,
        "mode": qr.mode,
        "amount_cents": qr.amount_cents,
        "currency_code": qr.currency_code,
        "expires_at": qr.expires_at.isoformat() + "Z",
    }


@router.post("/merchant/cpm_request")
def create_cpm_request(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_merchant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a merchant")
    amount_cents = payload.get("amount_cents")
    code = payload.get("code") or payload.get("scanned_text")
    if not isinstance(amount_cents, int) or amount_cents <= 0 or not isinstance(code, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    # Parse CPM code
    target: User | None = None
    if code.startswith("CPM:v1;phone="):
        phone = code.split("CPM:v1;phone=", 1)[1].strip()
        if not (phone.startswith("+") and phone[1:].isdigit() and len(phone) >= 8):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone format")
        target = db.query(User).filter(User.phone == phone).one_or_none()
        if target is None:
            from ..auth import ensure_user_and_wallet
            target = ensure_user_and_wallet(db, phone, None)
    elif code.startswith("CPM:v1;id="):
        uid = code.split("CPM:v1;id=", 1)[1].strip()
        target = db.get(User, uid)
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported CPM format")

    # Expiry
    exp = None
    try:
        if settings.REQUEST_EXPIRY_MINUTES:
            exp = datetime.utcnow() + timedelta(minutes=settings.REQUEST_EXPIRY_MINUTES)
    except Exception:
        pass

    pr = PaymentRequest(
        requester_user_id=user.id,
        target_user_id=target.id,
        amount_cents=amount_cents,
        currency_code=settings.DEFAULT_CURRENCY,
        status="pending",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        expires_at=exp,
        metadata_json={"source": "cpm", "via": "pos"},
    )
    db.add(pr)
    db.flush()
    record_event(db, "payments.cpm_request", str(user.id), {"amount_cents": amount_cents})
    return {"id": str(pr.id), "deeplink": f"payments://request/{pr.id}"}
