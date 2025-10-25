from sqlalchemy.orm import Session

from ..config import settings
from ..models import User, Wallet


def ensure_fee_wallet(db: Session) -> Wallet:
    phone = settings.FEE_WALLET_PHONE
    user = db.query(User).filter(User.phone == phone).one_or_none()
    if user is None:
        user = User(phone=phone, name="System Fees", is_merchant=False)
        db.add(user)
        db.flush()
        wallet = Wallet(user_id=user.id)
        db.add(wallet)
        db.flush()
        return wallet
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).one_or_none()
    if wallet is None:
        wallet = Wallet(user_id=user.id)
        db.add(wallet)
        db.flush()
    return wallet


def calc_fee_bps(amount_cents: int, bps: int) -> int:
    if bps <= 0 or amount_cents <= 0:
        return 0
    # Round to nearest cent using integer math
    return (amount_cents * bps + 5000) // 10000

