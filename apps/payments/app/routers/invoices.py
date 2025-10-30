from __future__ import annotations
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..auth import get_current_user, get_db, ensure_user_and_wallet
from ..config import settings
from ..database import SessionLocal
from ..models import User, Wallet, Invoice, EBillMandate, Transfer, LedgerEntry
from ..schemas import (
    InvoiceCreateIn,
    InvoiceOut,
    InvoicesListOut,
    MandateUpsertIn,
    MandateOut,
    MandatesListOut,
    TransferOut,
)
from ..utils.kyc_policy import enforce_tx_limits, require_min_kyc_level
from ..utils.audit import record_event
from ..utils.risk import evaluate_risk_and_maybe_block
from ..utils.idempotency_store import reserve as idem_reserve, finalize as idem_finalize


router = APIRouter(prefix="/invoices", tags=["invoices"])


def _to_invoice_out(db: Session, inv: Invoice) -> InvoiceOut:
    issuer = db.get(User, inv.issuer_user_id)
    payer = db.get(User, inv.payer_user_id)
    return InvoiceOut(
        id=str(inv.id),
        issuer_phone=issuer.phone if issuer else "",
        payer_phone=payer.phone if payer else "",
        amount_cents=inv.amount_cents,
        currency_code=inv.currency_code,
        status=inv.status,
        reference=inv.reference,
        description=inv.description,
        due_at=inv.due_at.isoformat() + "Z",
        created_at=inv.created_at.isoformat() + "Z",
        paid_transfer_id=str(inv.paid_transfer_id) if inv.paid_transfer_id else None,
    )


@router.post("", response_model=InvoiceOut)
def create_invoice(
    payload: InvoiceCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Require KYC and merchant flag to issue invoices
    require_min_kyc_level(user, 1)
    if not user.is_merchant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a merchant")

    payer = db.query(User).filter(User.phone == payload.payer_phone).one_or_none()
    if payer is None:
        # Allow creating invoice to a not-yet-onboarded user; ensure user+wallet exists
        payer = ensure_user_and_wallet(db, payload.payer_phone, None)
    if payer.id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot invoice yourself")

    due_at = datetime.utcnow() + timedelta(days=payload.due_in_days)
    inv = Invoice(
        issuer_user_id=user.id,
        payer_user_id=payer.id,
        amount_cents=payload.amount_cents,
        currency_code=settings.DEFAULT_CURRENCY,
        status="pending",
        reference=payload.reference,
        description=payload.description,
        due_at=due_at,
    )
    db.add(inv)
    db.flush()
    record_event(db, "invoices.create", str(user.id), {"payer": payload.payer_phone, "amount_cents": payload.amount_cents})
    return _to_invoice_out(db, inv)


@router.get("", response_model=InvoicesListOut)
def list_invoices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    incoming = (
        db.query(Invoice)
        .filter(Invoice.payer_user_id == user.id)
        .order_by(Invoice.created_at.desc())
        .limit(100)
        .all()
    )
    outgoing = (
        db.query(Invoice)
        .filter(Invoice.issuer_user_id == user.id)
        .order_by(Invoice.created_at.desc())
        .limit(100)
        .all()
    )
    return InvoicesListOut(incoming=[_to_invoice_out(db, i) for i in incoming], outgoing=[_to_invoice_out(db, i) for i in outgoing])


@router.post("/{invoice_id}/pay", response_model=TransferOut)
def pay_invoice(
    invoice_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idem_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).with_for_update().one_or_none()
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if inv.payer_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your invoice")
    if inv.status == "paid":
        # Return the underlying transfer if available
        if inv.paid_transfer_id:
            t = db.get(Transfer, inv.paid_transfer_id)
            return TransferOut(
                transfer_id=str(t.id),
                from_wallet_id=str(t.from_wallet_id) if t.from_wallet_id else None,
                to_wallet_id=str(t.to_wallet_id) if t.to_wallet_id else None,
                amount_cents=t.amount_cents,
                currency_code=t.currency_code,
                status=t.status,
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already paid")
    if inv.status in ("canceled", "expired"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot pay {inv.status} invoice")

    payer_wallet = db.query(Wallet).filter(Wallet.user_id == inv.payer_user_id).with_for_update().one()
    issuer_wallet = db.query(Wallet).filter(Wallet.user_id == inv.issuer_user_id).with_for_update().one()
    if payer_wallet.currency_code != issuer_wallet.currency_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Currency mismatch")
    if payer_wallet.balance_cents < inv.amount_cents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient balance")

    # KYC and risk checks for payer
    enforce_tx_limits(db, user, inv.amount_cents)
    try:
        evaluate_risk_and_maybe_block(db, user, inv.amount_cents, context="invoice_pay", merchant_user_id=str(inv.issuer_user_id))
    except HTTPException:
        raise

    # Attempt idempotent transfer with request fingerprint
    idem_rec = None
    if idem_key:
        idem_rec, state = idem_reserve(db, str(user.id), "POST", f"/invoices/{invoice_id}/pay", idem_key, {"invoice_id": invoice_id})
        if state == "replay" and idem_rec.result_ref:
            existing = db.query(Transfer).filter(Transfer.id == idem_rec.result_ref).one_or_none()
            if existing is not None:
                inv.status = "paid"
                inv.paid_transfer_id = existing.id
                inv.updated_at = datetime.utcnow()
                return TransferOut(
                    transfer_id=str(existing.id),
                    from_wallet_id=str(existing.from_wallet_id) if existing.from_wallet_id else None,
                    to_wallet_id=str(existing.to_wallet_id) if existing.to_wallet_id else None,
                    amount_cents=existing.amount_cents,
                    currency_code=existing.currency_code,
                    status=existing.status,
                )
    # Fallback to classic idempotency lookup
    if idem_key and (idem_rec is None):
        existing = db.query(Transfer).filter(Transfer.idempotency_key == idem_key).one_or_none()
        if existing is not None:
            inv.status = "paid"
            inv.paid_transfer_id = existing.id
            inv.updated_at = datetime.utcnow()
            return TransferOut(
                transfer_id=str(existing.id),
                from_wallet_id=str(existing.from_wallet_id) if existing.from_wallet_id else None,
                to_wallet_id=str(existing.to_wallet_id) if existing.to_wallet_id else None,
                amount_cents=existing.amount_cents,
                currency_code=existing.currency_code,
                status=existing.status,
            )

    try:
        t = Transfer(
            from_wallet_id=payer_wallet.id,
            to_wallet_id=issuer_wallet.id,
            amount_cents=inv.amount_cents,
            currency_code=payer_wallet.currency_code,
            status="completed",
            idempotency_key=idem_key,
        )
        db.add(t)
        db.flush()

        db.add_all([
            LedgerEntry(transfer_id=t.id, wallet_id=payer_wallet.id, amount_cents_signed=-inv.amount_cents),
            LedgerEntry(transfer_id=t.id, wallet_id=issuer_wallet.id, amount_cents_signed=inv.amount_cents),
        ])
        payer_wallet.balance_cents -= inv.amount_cents
        issuer_wallet.balance_cents += inv.amount_cents

        inv.status = "paid"
        inv.paid_transfer_id = t.id
        inv.updated_at = datetime.utcnow()
        record_event(db, "invoices.pay", str(user.id), {"invoice_id": str(inv.id), "amount_cents": inv.amount_cents})
        out = TransferOut(
            transfer_id=str(t.id),
            from_wallet_id=str(payer_wallet.id),
            to_wallet_id=str(issuer_wallet.id),
            amount_cents=inv.amount_cents,
            currency_code=payer_wallet.currency_code,
            status=t.status,
        )
        try:
            if idem_rec is not None:
                idem_finalize(db, idem_rec, str(t.id))
        except Exception:
            pass
        return out
    except IntegrityError:
        db.rollback()
        if idem_key:
            existing2 = db.query(Transfer).filter(Transfer.idempotency_key == idem_key).one_or_none()
            if existing2 is None:
                raise
            inv = db.query(Invoice).filter(Invoice.id == invoice_id).with_for_update().one()
            inv.status = "paid"
            inv.paid_transfer_id = existing2.id
            inv.updated_at = datetime.utcnow()
            out2 = TransferOut(
                transfer_id=str(existing2.id),
                from_wallet_id=str(existing2.from_wallet_id) if existing2.from_wallet_id else None,
                to_wallet_id=str(existing2.to_wallet_id) if existing2.to_wallet_id else None,
                amount_cents=existing2.amount_cents,
                currency_code=existing2.currency_code,
                status=existing2.status,
            )
            try:
                if idem_rec is not None:
                    idem_finalize(db, idem_rec, str(existing2.id))
            except Exception:
                pass
            return out2
        raise


@router.post("/process_due")
def process_due_invoices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Process due invoices with active autopay mandates for this user (payer)
    now = datetime.utcnow()
    # Find invoices where the current user is payer and due now
    rows: list[Invoice] = (
        db.query(Invoice)
        .filter(Invoice.payer_user_id == user.id)
        .filter(Invoice.status == "pending")
        .filter(Invoice.due_at <= now)
        .order_by(Invoice.due_at.asc())
        .limit(100)
        .all()
    )
    processed: list[str] = []
    errors: list[dict] = []
    for inv in rows:
        # Check mandate
        m = (
            db.query(EBillMandate)
            .filter(EBillMandate.payer_user_id == inv.payer_user_id, EBillMandate.issuer_user_id == inv.issuer_user_id, EBillMandate.status == "active")
            .one_or_none()
        )
        if not m or not m.autopay:
            continue
        if m.max_amount_cents is not None and inv.amount_cents > m.max_amount_cents:
            continue
        try:
            # Use deterministic idempotency key
            idem = f"auto-invoice-{inv.id}"
            pay_invoice(str(inv.id), user=user, db=db, idem_key=idem)  # type: ignore[arg-type]
            processed.append(str(inv.id))
        except HTTPException as he:
            errors.append({"id": str(inv.id), "error": he.detail})
        except Exception:
            errors.append({"id": str(inv.id), "error": "unknown"})
    return {"processed": processed, "errors": errors}


def process_all_due_once():
    """Process all due invoices for all payers with active autopay mandates (best-effort)."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        # Fetch a batch of due invoices with active autopay mandate
        # We avoid joins for simplicity and iterate with filters
        due = (
            db.query(Invoice)
            .filter(Invoice.status == "pending")
            .filter(Invoice.due_at <= now)
            .order_by(Invoice.due_at.asc())
            .limit(500)
            .all()
        )
        processed = 0
        for inv in due:
            m = (
                db.query(EBillMandate)
                .filter(
                    EBillMandate.payer_user_id == inv.payer_user_id,
                    EBillMandate.issuer_user_id == inv.issuer_user_id,
                    EBillMandate.status == "active",
                )
                .one_or_none()
            )
            if not m or not m.autopay:
                continue
            if m.max_amount_cents is not None and inv.amount_cents > m.max_amount_cents:
                continue
            try:
                payer = db.get(User, inv.payer_user_id)
                idem = f"auto-invoice-{inv.id}"
                pay_invoice(str(inv.id), user=payer, db=db, idem_key=idem)  # type: ignore[arg-type]
                processed += 1
            except Exception:
                db.rollback()
                continue
        db.commit()
        return {"processed": processed}
    finally:
        db.close()


@router.post("/mandates", response_model=MandateOut)
def upsert_mandate(
    payload: MandateUpsertIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    issuer = db.query(User).filter(User.phone == payload.issuer_phone).one_or_none()
    if issuer is None:
        issuer = ensure_user_and_wallet(db, payload.issuer_phone, None)
    # Upsert by payer+issuer pair
    existing = (
        db.query(EBillMandate)
        .filter(EBillMandate.payer_user_id == user.id, EBillMandate.issuer_user_id == issuer.id)
        .one_or_none()
    )
    if existing is None:
        m = EBillMandate(
            payer_user_id=user.id,
            issuer_user_id=issuer.id,
            autopay=payload.autopay,
            max_amount_cents=payload.max_amount_cents,
            status="active",
        )
        db.add(m)
        db.flush()
    else:
        existing.autopay = payload.autopay
        existing.max_amount_cents = payload.max_amount_cents
        existing.updated_at = datetime.utcnow()
        m = existing
    record_event(db, "invoices.mandate_upsert", str(user.id), {"issuer": payload.issuer_phone, "autopay": payload.autopay})
    return MandateOut(
        id=str(m.id),
        issuer_phone=payload.issuer_phone,
        autopay=m.autopay,
        max_amount_cents=m.max_amount_cents,
        status=m.status,
        created_at=m.created_at.isoformat() + "Z",
        updated_at=m.updated_at.isoformat() + "Z",
    )


@router.get("/mandates", response_model=MandatesListOut)
def list_mandates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(EBillMandate)
        .filter(EBillMandate.payer_user_id == user.id)
        .order_by(EBillMandate.created_at.desc())
        .limit(100)
        .all()
    )
    items: list[MandateOut] = []
    for m in rows:
        issuer = db.get(User, m.issuer_user_id)
        items.append(
            MandateOut(
                id=str(m.id),
                issuer_phone=issuer.phone if issuer else "",
                autopay=m.autopay,
                max_amount_cents=m.max_amount_cents,
                status=m.status,
                created_at=m.created_at.isoformat() + "Z",
                updated_at=m.updated_at.isoformat() + "Z",
            )
        )
    return MandatesListOut(items=items)


@router.post("/{invoice_id}/dev_force_due")
def dev_force_due(invoice_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # DEV only: move due_at to past to simulate due invoices
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if inv.payer_user_id != user.id and inv.issuer_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    inv.due_at = datetime.utcnow() - timedelta(minutes=1)
    inv.updated_at = datetime.utcnow()
    return {"ok": True}
