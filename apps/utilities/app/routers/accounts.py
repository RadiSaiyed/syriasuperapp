from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import User, Biller, BillerAccount
from ..schemas import LinkAccountIn, AccountOut


router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("/link", response_model=AccountOut)
def link_account(payload: LinkAccountIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    biller = db.get(Biller, payload.biller_id)
    if biller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Biller not found")
    acc = BillerAccount(user_id=user.id, biller_id=biller.id, account_ref=payload.account_ref, alias=payload.alias)
    db.add(acc)
    db.flush()
    return AccountOut(id=str(acc.id), biller_id=str(acc.biller_id), account_ref=acc.account_ref, alias=acc.alias)


@router.get("", response_model=list[AccountOut])
def list_accounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(BillerAccount).filter(BillerAccount.user_id == user.id).order_by(BillerAccount.created_at.desc()).all()
    return [AccountOut(id=str(a.id), biller_id=str(a.biller_id), account_ref=a.account_ref, alias=a.alias) for a in rows]


@router.put("/{account_id}", response_model=AccountOut)
def update_account(account_id: str, alias: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(BillerAccount, account_id)
    if a is None or a.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    a.alias = (alias or "").strip() or None
    db.flush()
    return AccountOut(id=str(a.id), biller_id=str(a.biller_id), account_ref=a.account_ref, alias=a.alias)


@router.delete("/{account_id}")
def delete_account(account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(BillerAccount, account_id)
    if a is None or a.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    db.delete(a)
    return {"detail": "deleted"}
