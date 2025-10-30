from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..config import settings
from ..models import User, Wallet, CashRequest, Transfer, LedgerEntry
from ..schemas import CashRequestCreateIn, CashRequestOut, CashRequestsListOut
from ..utils.kyc_policy import enforce_tx_limits
from ..utils.fees import ensure_fee_wallet, calc_fee_bps


router = APIRouter(prefix="/cash", tags=["cash"])


def _to_out(db: Session, r: CashRequest) -> CashRequestOut:
    user = db.get(User, r.user_id)
    agent = db.get(User, r.agent_user_id) if r.agent_user_id else None
    return CashRequestOut(
        id=str(r.id),
        type=r.type,
        user_phone=user.phone if user else "",
        agent_phone=agent.phone if agent else None,
        amount_cents=r.amount_cents,
        currency_code=r.currency_code,
        status=r.status,
        created_at=r.created_at.isoformat() + "Z",
    )


@router.post("/agents/dev/become_agent")
def dev_become_agent(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.is_agent = True
    db.flush()
    return {"detail": "agent enabled"}


@router.post("/cashin/request", response_model=CashRequestOut)
def create_cashin(
    payload: CashRequestCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idem_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if idem_key:
        existing = db.query(CashRequest).filter(CashRequest.idempotency_key == idem_key).one_or_none()
        if existing is not None:
            return _to_out(db, existing)
    r = CashRequest(type="cashin", user_id=user.id, amount_cents=payload.amount_cents, currency_code=settings.DEFAULT_CURRENCY, idempotency_key=idem_key)
    db.add(r)
    db.flush()
    return _to_out(db, r)


@router.post("/cashout/request", response_model=CashRequestOut)
def create_cashout(
    payload: CashRequestCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idem_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    # Enforce that user has funds for the requested amount at time of request? Optional; enforce on accept.
    if idem_key:
        existing = db.query(CashRequest).filter(CashRequest.idempotency_key == idem_key).one_or_none()
        if existing is not None:
            return _to_out(db, existing)
    r = CashRequest(type="cashout", user_id=user.id, amount_cents=payload.amount_cents, currency_code=settings.DEFAULT_CURRENCY, idempotency_key=idem_key)
    db.add(r)
    db.flush()
    return _to_out(db, r)


@router.get("/requests", response_model=CashRequestsListOut)
def list_cash_requests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    my = db.query(CashRequest).filter(CashRequest.user_id == user.id).order_by(CashRequest.created_at.desc()).limit(100).all()
    incoming = []
    if user.is_agent:
        incoming = (
            db.query(CashRequest)
            .filter(CashRequest.status == "pending")
            .order_by(CashRequest.created_at.asc())
            .limit(200)
            .all()
        )
    return CashRequestsListOut(my=[_to_out(db, r) for r in my], incoming=[_to_out(db, r) for r in incoming])


@router.post("/requests/{request_id}/accept")
def accept_cash_request(request_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_agent:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an agent")
    r = db.get(CashRequest, request_id)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if r.status != "pending":
        return {"detail": f"already {r.status}"}
    # Lock both wallets
    agent_wallet = db.query(Wallet).filter(Wallet.user_id == user.id).with_for_update().one()
    customer_wallet = db.query(Wallet).filter(Wallet.user_id == r.user_id).with_for_update().one()

    amount = r.amount_cents
    fee_wallet = ensure_fee_wallet(db)
    if r.type == "cashin":
        # Cash-in: agent pays cash to user; fee charged to agent
        fee = calc_fee_bps(amount, settings.CASHIN_FEE_BPS)
        total_agent_debit = amount + fee
        if agent_wallet.balance_cents < total_agent_debit:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent insufficient balance")
        # Main transfer agent -> user
        t = Transfer(from_wallet_id=agent_wallet.id, to_wallet_id=customer_wallet.id, amount_cents=amount, currency_code=agent_wallet.currency_code, status="completed")
        db.add(t); db.flush()
        db.add_all([
            LedgerEntry(transfer_id=t.id, wallet_id=agent_wallet.id, amount_cents_signed=-amount),
            LedgerEntry(transfer_id=t.id, wallet_id=customer_wallet.id, amount_cents_signed=amount),
        ])
        agent_wallet.balance_cents -= amount
        customer_wallet.balance_cents += amount
        # Fee transfer agent -> fee wallet
        if fee > 0:
            tfee = Transfer(from_wallet_id=agent_wallet.id, to_wallet_id=fee_wallet.id, amount_cents=fee, currency_code=agent_wallet.currency_code, status="completed")
            db.add(tfee); db.flush()
            db.add_all([
                LedgerEntry(transfer_id=tfee.id, wallet_id=agent_wallet.id, amount_cents_signed=-fee),
                LedgerEntry(transfer_id=tfee.id, wallet_id=fee_wallet.id, amount_cents_signed=fee),
            ])
            agent_wallet.balance_cents -= fee
            fee_wallet.balance_cents += fee
    else:
        # Cash-out: user withdraws; fee charged to user
        customer_user = db.get(User, r.user_id)
        enforce_tx_limits(db, customer_user, amount)
        fee = calc_fee_bps(amount, settings.CASHOUT_FEE_BPS)
        total_user_debit = amount + fee
        if customer_wallet.balance_cents < total_user_debit:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient balance")
        # Main transfer user -> agent
        t = Transfer(from_wallet_id=customer_wallet.id, to_wallet_id=agent_wallet.id, amount_cents=amount, currency_code=customer_wallet.currency_code, status="completed")
        db.add(t); db.flush()
        db.add_all([
            LedgerEntry(transfer_id=t.id, wallet_id=customer_wallet.id, amount_cents_signed=-amount),
            LedgerEntry(transfer_id=t.id, wallet_id=agent_wallet.id, amount_cents_signed=amount),
        ])
        customer_wallet.balance_cents -= amount
        agent_wallet.balance_cents += amount
        # Fee transfer user -> fee wallet
        if fee > 0:
            tfee = Transfer(from_wallet_id=customer_wallet.id, to_wallet_id=fee_wallet.id, amount_cents=fee, currency_code=customer_wallet.currency_code, status="completed")
            db.add(tfee); db.flush()
            db.add_all([
                LedgerEntry(transfer_id=tfee.id, wallet_id=customer_wallet.id, amount_cents_signed=-fee),
                LedgerEntry(transfer_id=tfee.id, wallet_id=fee_wallet.id, amount_cents_signed=fee),
            ])
            customer_wallet.balance_cents -= fee
            fee_wallet.balance_cents += fee

    r.status = "completed"
    r.agent_user_id = user.id
    r.updated_at = datetime.utcnow()
    db.flush()
    return {"detail": "completed"}


@router.post("/requests/{request_id}/reject")
def reject_cash_request(request_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_agent:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an agent")
    r = db.get(CashRequest, request_id)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if r.status != "pending":
        return {"detail": f"already {r.status}"}
    r.status = "rejected"
    r.updated_at = datetime.utcnow()
    db.flush()
    return {"detail": "rejected"}


@router.post("/requests/{request_id}/cancel")
def cancel_cash_request(request_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(CashRequest, request_id)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if r.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not owner")
    if r.status != "pending":
        return {"detail": f"already {r.status}"}
    r.status = "canceled"
    r.updated_at = datetime.utcnow()
    db.flush()
    return {"detail": "canceled"}
