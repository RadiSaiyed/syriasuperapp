from datetime import datetime
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Response
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db, ensure_user_and_wallet
from ..models import User, Wallet, Transfer, LedgerEntry, TopupVoucher
from ..schemas import (
    VoucherCreateIn,
    VoucherOut,
    VouchersListOut,
    VouchersBulkCreateIn,
    VouchersAdminSummaryOut,
    VoucherAdminItem,
    VouchersAdminListOut,
)
from .admin import require_admin


router = APIRouter(prefix="/vouchers", tags=["vouchers"])


def _to_out(v: TopupVoucher) -> VoucherOut:
    return VoucherOut(
        id=str(v.id),
        code=v.code,
        amount_cents=v.amount_cents,
        amount_syp=max(0, int(v.amount_cents // 100)),
        currency_code=v.currency_code,
        status=v.status,
        qr_text=f"VCHR|{v.code}",
        created_at=v.created_at.isoformat() + "Z",
        redeemed_at=(v.redeemed_at.isoformat() + "Z") if v.redeemed_at else None,
    )


@router.post("", response_model=VoucherOut)
def create_voucher(payload: VoucherCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.amount_syp <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")
    # Generate unique code (short, URL-safe)
    # 16 bytes => 22 chars URL-safe base64 (we'll hex to keep simple)
    for _ in range(5):
        code = secrets.token_hex(8)
        if db.query(TopupVoucher).filter(TopupVoucher.code == code).one_or_none() is None:
            break
    else:
        raise HTTPException(status_code=500, detail="Could not generate code")
    v = TopupVoucher(
        code=code,
        amount_cents=payload.amount_syp * 100,
        currency_code=payload.currency_code or "SYP",
        status="active",
        created_by_user_id=user.id,
    )
    db.add(v)
    db.flush()
    return _to_out(v)


@router.get("", response_model=VouchersListOut)
def list_my_vouchers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(TopupVoucher)
        .filter(TopupVoucher.created_by_user_id == user.id)
        .order_by(TopupVoucher.created_at.desc())
        .limit(200)
        .all()
    )
    return VouchersListOut(items=[_to_out(v) for v in rows])


@router.post("/{code}/redeem", response_model=VoucherOut)
def redeem_voucher(code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    v = db.query(TopupVoucher).filter(TopupVoucher.code == code).with_for_update().one_or_none()
    if v is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voucher not found")
    if v.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Voucher not active")
    if v.amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Invalid voucher amount")

    # Compute fee (default 1%) and split mint between user and fee wallet
    total = int(v.amount_cents)
    from ..config import settings
    bps = max(0, int(getattr(settings, "VOUCHER_FEE_BPS", 100)))
    fee = int((total * bps + 5000) // 10000)
    fee = min(max(0, fee), total)
    net = total - fee

    # Credit user's wallet (net)
    w = db.query(Wallet).filter(Wallet.user_id == user.id).with_for_update().one()
    t_user = Transfer(
        from_wallet_id=None,
        to_wallet_id=w.id,
        amount_cents=net,
        currency_code=w.currency_code,
        status="completed",
        idempotency_key=f"voucher:{v.code}:net",
    )
    db.add(t_user)
    db.flush()
    db.add(LedgerEntry(transfer_id=t_user.id, wallet_id=w.id, amount_cents_signed=net))
    w.balance_cents = w.balance_cents + net

    # Credit fee wallet (fee), if fee > 0
    if fee > 0:
        fee_phone = settings.FEE_WALLET_PHONE
        fee_user = ensure_user_and_wallet(db, fee_phone, name="Platform Fee")
        fee_wallet = db.query(Wallet).filter(Wallet.user_id == fee_user.id).with_for_update().one()
        t_fee = Transfer(
            from_wallet_id=None,
            to_wallet_id=fee_wallet.id,
            amount_cents=fee,
            currency_code=fee_wallet.currency_code,
            status="completed",
            idempotency_key=f"voucher:{v.code}:fee",
        )
        db.add(t_fee)
        db.flush()
        db.add(LedgerEntry(transfer_id=t_fee.id, wallet_id=fee_wallet.id, amount_cents_signed=fee))
        fee_wallet.balance_cents = fee_wallet.balance_cents + fee

    v.status = "redeemed"
    v.redeemed_by_user_id = user.id
    v.redeemed_at = datetime.utcnow()
    db.flush()
    return _to_out(v)


@router.post("/admin/vouchers/bulk", response_model=VouchersListOut)
def admin_vouchers_bulk(
    payload: VouchersBulkCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    if payload.amount_syp <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")
    count = int(payload.count)
    items: list[TopupVoucher] = []
    prefix = (payload.prefix or "").strip()
    if prefix:
        # sanitize: alnum only
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,10}", prefix):
            raise HTTPException(status_code=400, detail="Invalid prefix")
    for _ in range(count):
        for _try in range(5):
            code = secrets.token_hex(8)
            if prefix:
                code = f"{prefix}{code}"
            if db.query(TopupVoucher).filter(TopupVoucher.code == code).one_or_none() is None:
                v = TopupVoucher(
                    code=code,
                    amount_cents=payload.amount_syp * 100,
                    currency_code=payload.currency_code or "SYP",
                    status="active",
                    created_by_user_id=user.id,
                )
                db.add(v)
                items.append(v)
                break
        else:
            raise HTTPException(status_code=500, detail="Failed to generate unique code")
    db.flush()
    # Return most recent created items
    return VouchersListOut(items=[_to_out(v) for v in items])


@router.get("/admin/summary", response_model=VouchersAdminSummaryOut)
def admin_vouchers_summary(
    created_by: str | None = None,  # "me" to restrict to current user
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    q = db.query(TopupVoucher)
    if created_by == "me":
        q = q.filter(TopupVoucher.created_by_user_id == user.id)
    rows = q.all()
    total = len(rows)
    active = sum(1 for v in rows if v.status == "active")
    redeemed = sum(1 for v in rows if v.status == "redeemed")
    revoked = sum(1 for v in rows if v.status == "revoked")
    sum_total_cents = sum(int(v.amount_cents) for v in rows)
    sum_redeemed_cents = sum(int(v.amount_cents) for v in rows if v.status == "redeemed")
    from ..config import settings
    bps = max(0, int(getattr(settings, "VOUCHER_FEE_BPS", 100)))
    fees_cents = (sum_redeemed_cents * bps + 5000) // 10000
    net_cents = sum_redeemed_cents - fees_cents
    return VouchersAdminSummaryOut(
        total_count=total,
        active_count=active,
        redeemed_count=redeemed,
        revoked_count=revoked,
        total_syp=int(sum_total_cents // 100),
        redeemed_total_syp=int(sum_redeemed_cents // 100),
        fees_syp=int(fees_cents // 100),
        net_syp=int(net_cents // 100),
    )


@router.get("/admin/list", response_model=VouchersAdminListOut)
def admin_vouchers_list(
    status: str | None = None,  # active|redeemed|revoked
    prefix: str | None = None,
    created_by: str | None = None,  # "me"
    limit: int = 200,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    limit = max(1, min(1000, int(limit)))
    q = db.query(TopupVoucher)
    if status in {"active", "redeemed", "revoked"}:
        q = q.filter(TopupVoucher.status == status)
    if prefix:
        q = q.filter(TopupVoucher.code.like(f"{prefix}%"))
    if created_by == "me":
        q = q.filter(TopupVoucher.created_by_user_id == user.id)
    rows = (
        q.order_by(TopupVoucher.created_at.desc())
        .limit(limit)
        .all()
    )
    out: list[VoucherAdminItem] = []
    for v in rows:
        creator = db.get(User, v.created_by_user_id) if v.created_by_user_id else None
        redeemer = db.get(User, v.redeemed_by_user_id) if v.redeemed_by_user_id else None
        out.append(
            VoucherAdminItem(
                id=str(v.id),
                code=v.code,
                amount_syp=int(v.amount_cents // 100),
                status=v.status,
                created_at=v.created_at.isoformat() + "Z",
                redeemed_at=(v.redeemed_at.isoformat() + "Z") if v.redeemed_at else None,
                created_by_phone=creator.phone if creator else None,
                redeemed_by_phone=redeemer.phone if redeemer else None,
            )
        )
    return VouchersAdminListOut(items=out)


@router.post("/admin/{code}/revoke", response_model=VoucherOut)
def admin_voucher_revoke(
    code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    v = db.query(TopupVoucher).filter(TopupVoucher.code == code).with_for_update().one_or_none()
    if v is None:
        raise HTTPException(status_code=404, detail="Voucher not found")
    if v.status != "active":
        raise HTTPException(status_code=400, detail="Cannot revoke non-active voucher")
    v.status = "revoked"
    db.flush()
    return _to_out(v)


@router.get("/admin/export")
def admin_vouchers_export(
    status: str | None = None,
    prefix: str | None = None,
    created_by: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    # Produce CSV with columns: code,amount_syp,status,created_at,redeemed_at,created_by_phone,redeemed_by_phone,qr_text
    q = db.query(TopupVoucher)
    if status in {"active", "redeemed", "revoked"}:
        q = q.filter(TopupVoucher.status == status)
    if prefix:
        q = q.filter(TopupVoucher.code.like(f"{prefix}%"))
    if created_by == "me":
        q = q.filter(TopupVoucher.created_by_user_id == user.id)
    rows = q.order_by(TopupVoucher.created_at.desc()).all()
    import csv
    from io import StringIO
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["code", "amount_syp", "status", "created_at", "redeemed_at", "created_by_phone", "redeemed_by_phone", "qr_text"])
    for v in rows:
        creator = db.get(User, v.created_by_user_id) if v.created_by_user_id else None
        redeemer = db.get(User, v.redeemed_by_user_id) if v.redeemed_by_user_id else None
        w.writerow([
            v.code,
            int(v.amount_cents // 100),
            v.status,
            (v.created_at.isoformat() + "Z") if v.created_at else "",
            (v.redeemed_at.isoformat() + "Z") if v.redeemed_at else "",
            (creator.phone if creator else ""),
            (redeemer.phone if redeemer else ""),
            f"VCHR|{v.code}",
        ])
    return Response(buf.getvalue(), media_type="text/csv")


@router.get("/admin/fees/entries")
def admin_fees_entries(
    limit: int = 200,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    limit = max(1, min(1000, int(limit)))
    # List fee transfers credited to fee wallet for vouchers redeem
    from ..models import Transfer
    q = db.query(Transfer).filter(Transfer.idempotency_key.like("voucher:%:fee")).order_by(Transfer.created_at.desc()).limit(limit)
    rows = q.all()
    out = []
    for t in rows:
        # Extract voucher code between 'voucher:' and ':fee'
        code = ""
        key = t.idempotency_key or ""
        try:
            if key.startswith("voucher:") and key.endswith(":fee"):
                code = key[len("voucher:"):-len(":fee")]
        except Exception:
            code = key
        out.append({
            "transfer_id": str(t.id),
            "code": code,
            "amount_cents": int(t.amount_cents),
            "amount_syp": int(t.amount_cents // 100),
            "created_at": t.created_at.isoformat() + "Z",
        })
    return {"items": out}
