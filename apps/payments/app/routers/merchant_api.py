from fastapi import APIRouter, Depends, Header, HTTPException, status, Request
from sqlalchemy.orm import Session
from ..auth import get_db, get_current_user
from ..models import User, Wallet, LedgerEntry, MerchantApiKey
from ..utils.merchant_api import verify_request


router = APIRouter(prefix="/merchant/api", tags=["merchant-api"])


@router.post("/keys")
def create_key(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_merchant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Merchant only")
    import secrets
    key_id = secrets.token_hex(8)
    secret = secrets.token_hex(16)
    rec = MerchantApiKey(user_id=user.id, key_id=key_id, secret=secret, scope="transactions:read")
    db.add(rec); db.flush()
    return {"key_id": key_id, "secret": secret}


@router.get("/keys")
def list_keys(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_merchant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Merchant only")
    rows = db.query(MerchantApiKey).filter(MerchantApiKey.user_id == user.id).order_by(MerchantApiKey.created_at.desc()).all()
    return [{"key_id": r.key_id, "created_at": r.created_at.isoformat() + "Z"} for r in rows]


@router.delete("/keys/{key_id}")
def delete_key(key_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_merchant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Merchant only")
    rec = db.query(MerchantApiKey).filter(MerchantApiKey.user_id == user.id, MerchantApiKey.key_id == key_id).one_or_none()
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    db.delete(rec)
    return {"detail": "deleted"}


@router.post("/transactions")
def merchant_transactions(
    request: Request,
    db: Session = Depends(get_db),
    key_id: str | None = Header(default=None, alias="X-API-Key"),
    sign: str | None = Header(default=None, alias="X-API-Sign"),
    ts: str | None = Header(default=None, alias="X-API-Ts"),
):
    if not key_id or not sign or not ts:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing headers")
    body = b""  # POST with empty body for listing
    user_id = verify_request(db, key_id, sign, ts, str(request.url.path), body)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    # Scope check (default deny)
    rec = db.query(MerchantApiKey).filter(MerchantApiKey.key_id == key_id).one()
    scopes = {s.strip() for s in (rec.scope or "").split(",") if s.strip()}
    if not scopes or "transactions:read" not in scopes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")
    w = db.query(Wallet).filter(Wallet.user_id == user_id).one()
    rows = db.query(LedgerEntry).filter(LedgerEntry.wallet_id == w.id).order_by(LedgerEntry.created_at.desc()).limit(100).all()
    return {
        "wallet_id": str(w.id),
        "entries": [
            {
                "transfer_id": str(e.transfer_id),
                "amount_cents_signed": e.amount_cents_signed,
                "created_at": e.created_at.isoformat() + "Z",
            }
            for e in rows
        ],
    }
