from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..auth import get_current_user, get_db
from ..config import settings
from ..models import Wallet, User, Transfer, LedgerEntry
from ..schemas import (
    WalletResponse,
    WalletOut,
    UserOut,
    TopupIn,
    TransferIn,
    TransferOut,
    TransactionsOut,
    LedgerEntryOut,
)
from ..utils.idempotency import resolve_idempotency_key
from ..utils.kyc_policy import enforce_tx_limits
from ..utils.audit import record_event
from prometheus_client import Counter
from ..utils.fraud import check_p2p_velocity
from ..utils.risk import evaluate_risk_and_maybe_block
from ..utils.idempotency_store import reserve as idem_reserve, finalize as idem_finalize

TX_COUNTER = Counter("payments_transfers_total", "Transfers", ["kind", "status"])


router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("", response_model=WalletResponse)
def get_wallet(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).one()
    return WalletResponse(
        user=UserOut(id=str(user.id), phone=user.phone, name=user.name, is_merchant=user.is_merchant),
        wallet=WalletOut(id=str(wallet.id), balance_cents=wallet.balance_cents, currency_code=wallet.currency_code),
    )


@router.post("/topup", response_model=TransferOut)
def dev_topup(
    payload: TopupIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idem_hdr: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if not settings.DEV_ENABLE_TOPUP:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Topup disabled")

    # Idempotency on transfers.idempotency_key
    idem_key = resolve_idempotency_key(idem_hdr, getattr(payload, "idempotency_key", None))
    idem_rec = None
    # Reserve idempotency using request fingerprint (method+path+body hash)
    request = None  # idempotency reservation via request fingerprint disabled here
    if request is not None:
        idem_rec, state = idem_reserve(db, str(user.id), request.method, request.url.path, idem_key, payload)
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

    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).with_for_update().one()
    if payload.amount_cents <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid amount")

    try:
        transfer = Transfer(
            from_wallet_id=None,
            to_wallet_id=wallet.id,
            amount_cents=payload.amount_cents,
            currency_code=wallet.currency_code,
            status="completed",
            idempotency_key=idem_key,
        )
        db.add(transfer)
        db.flush()

        credit = LedgerEntry(transfer_id=transfer.id, wallet_id=wallet.id, amount_cents_signed=payload.amount_cents)
        db.add(credit)
        wallet.balance_cents = wallet.balance_cents + payload.amount_cents
        db.flush()

        out = TransferOut(
            transfer_id=str(transfer.id),
            from_wallet_id=None,
            to_wallet_id=str(wallet.id),
            amount_cents=payload.amount_cents,
            currency_code=wallet.currency_code,
            status=transfer.status,
        )
        try:
            if idem_rec is not None:
                idem_finalize(db, idem_rec, str(transfer.id))
        except Exception:
            pass
        record_event(db, "wallet.topup", str(user.id), {"amount_cents": payload.amount_cents})
        try:
            TX_COUNTER.labels("topup", transfer.status).inc()
        except Exception:
            pass
        return out
    except IntegrityError:
        db.rollback()
        existing2 = db.query(Transfer).filter(Transfer.idempotency_key == idem_key).one_or_none()
        if existing2 is None:
            raise
        try:
            TX_COUNTER.labels("topup", existing2.status).inc()
        except Exception:
            pass
        return TransferOut(
            transfer_id=str(existing2.id),
            from_wallet_id=str(existing2.from_wallet_id) if existing2.from_wallet_id else None,
            to_wallet_id=str(existing2.to_wallet_id) if existing2.to_wallet_id else None,
            amount_cents=existing2.amount_cents,
            currency_code=existing2.currency_code,
            status=existing2.status,
        )


@router.post("/transfer", response_model=TransferOut)
def p2p_transfer(
    payload: TransferIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idem_hdr: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if payload.amount_cents <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid amount")
    if payload.to_phone == user.phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot transfer to self")

    idem_key = resolve_idempotency_key(idem_hdr, getattr(payload, "idempotency_key", None))
    idem_rec = None
    # Reserve idempotency (conflict on mismatched payload)
    request = None
    if request is not None:
        idem_rec, state = idem_reserve(db, str(user.id), request.method, request.url.path, idem_key, payload)
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

    sender_wallet = (
        db.query(Wallet).join(User, Wallet.user_id == User.id).filter(User.id == user.id).with_for_update().one()
    )
    recipient = db.query(User).filter(User.phone == payload.to_phone).one_or_none()
    if recipient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")
    recipient_wallet = db.query(Wallet).filter(Wallet.user_id == recipient.id).with_for_update().one()

    if sender_wallet.currency_code != recipient_wallet.currency_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Currency mismatch")

    # Re-check idempotency after acquiring locks (avoid races)
    existing2 = db.query(Transfer).filter(Transfer.idempotency_key == idem_key).one_or_none()
    if existing2:
        return TransferOut(
            transfer_id=str(existing2.id),
            from_wallet_id=str(existing2.from_wallet_id) if existing2.from_wallet_id else None,
            to_wallet_id=str(existing2.to_wallet_id),
            amount_cents=existing2.amount_cents,
            currency_code=existing2.currency_code,
            status=existing2.status,
        )

    if sender_wallet.balance_cents < payload.amount_cents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient balance")

    # KYC: enforce limits for sender
    enforce_tx_limits(db, user, payload.amount_cents)
    # Velocity limits
    check_p2p_velocity(db, user, payload.amount_cents)
    # Risk engine (optional)
    try:
        evaluate_risk_and_maybe_block(db, user, payload.amount_cents, context="p2p_transfer")
    except HTTPException:
        raise

    try:
        transfer = Transfer(
            from_wallet_id=sender_wallet.id,
            to_wallet_id=recipient_wallet.id,
            amount_cents=payload.amount_cents,
            currency_code=sender_wallet.currency_code,
            status="completed",
            idempotency_key=idem_key,
        )
        db.add(transfer)
        db.flush()

        debit = LedgerEntry(transfer_id=transfer.id, wallet_id=sender_wallet.id, amount_cents_signed=-payload.amount_cents)
        credit = LedgerEntry(transfer_id=transfer.id, wallet_id=recipient_wallet.id, amount_cents_signed=payload.amount_cents)
        db.add_all([debit, credit])

        sender_wallet.balance_cents = sender_wallet.balance_cents - payload.amount_cents
        recipient_wallet.balance_cents = recipient_wallet.balance_cents + payload.amount_cents
        db.flush()

        out = TransferOut(
            transfer_id=str(transfer.id),
            from_wallet_id=str(sender_wallet.id),
            to_wallet_id=str(recipient_wallet.id),
            amount_cents=payload.amount_cents,
            currency_code=sender_wallet.currency_code,
            status=transfer.status,
        )
        try:
            if idem_rec is not None:
                idem_finalize(db, idem_rec, str(transfer.id))
        except Exception:
            pass
        record_event(db, "wallet.transfer", str(user.id), {"to": recipient.phone, "amount_cents": payload.amount_cents})
        try:
            TX_COUNTER.labels("p2p", transfer.status).inc()
        except Exception:
            pass
        return out
    except IntegrityError:
        db.rollback()
        existing3 = db.query(Transfer).filter(Transfer.idempotency_key == idem_key).one_or_none()
        if existing3 is None:
            raise
        try:
            TX_COUNTER.labels("p2p", existing3.status).inc()
        except Exception:
            pass
        return TransferOut(
            transfer_id=str(existing3.id),
            from_wallet_id=str(existing3.from_wallet_id) if existing3.from_wallet_id else None,
            to_wallet_id=str(existing3.to_wallet_id) if existing3.to_wallet_id else None,
            amount_cents=existing3.amount_cents,
            currency_code=existing3.currency_code,
            status=existing3.status,
        )


@router.get("/transactions", response_model=TransactionsOut)
def list_transactions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).one()
    q = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.wallet_id == wallet.id)
        .order_by(LedgerEntry.created_at.desc())
        .limit(100)
        .all()
    )
    entries = [
        LedgerEntryOut(
            transfer_id=str(e.transfer_id),
            wallet_id=str(e.wallet_id),
            amount_cents_signed=e.amount_cents_signed,
            created_at=e.created_at.isoformat() + "Z",
        )
        for e in q
    ]
    return TransactionsOut(entries=entries)


@router.get("/transactions/page")
def list_transactions_page(page: int = 1, page_size: int = 50, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page = max(1, page)
    page_size = min(max(1, page_size), 500)
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).one()
    base = db.query(LedgerEntry).filter(LedgerEntry.wallet_id == wallet.id)
    total = base.count()
    rows = (
        base.order_by(LedgerEntry.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "entries": [
            {
                "transfer_id": str(e.transfer_id),
                "wallet_id": str(e.wallet_id),
                "amount_cents_signed": e.amount_cents_signed,
                "created_at": e.created_at.isoformat() + "Z",
            }
            for e in rows
        ],
    }


@router.get("/transactions/export")
def export_transactions(format: str = "csv", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from fastapi import Response
    import csv
    from io import StringIO

    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).one()
    rows = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.wallet_id == wallet.id)
        .order_by(LedgerEntry.created_at.desc())
        .limit(1000)
        .all()
    )

    if format.lower() == "csv":
        buf = StringIO()
        w = csv.writer(buf)
        w.writerow(["created_at", "transfer_id", "wallet_id", "amount_cents_signed"])
        for e in rows:
            w.writerow([e.created_at.isoformat() + "Z", str(e.transfer_id), str(e.wallet_id), e.amount_cents_signed])
        data = buf.getvalue().encode()
        return Response(content=data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=transactions.csv"})
    else:
        # Fallback JSON
        return {
            "entries": [
                {
                    "transfer_id": str(e.transfer_id),
                    "wallet_id": str(e.wallet_id),
                    "amount_cents_signed": e.amount_cents_signed,
                    "created_at": e.created_at.isoformat() + "Z",
                }
                for e in rows
            ]
        }
