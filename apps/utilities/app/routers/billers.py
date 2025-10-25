from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from ..auth import get_current_user, get_db
from ..models import User, Biller, BillerProduct
from ..schemas import BillerOut
from fastapi import Query


router = APIRouter(prefix="/billers", tags=["billers"])


def _seed_dev(db: Session):
    if db.query(Biller).count() > 0:
        return
    elec = Biller(name="Electricity Co.", category="electricity")
    water = Biller(name="Water Co.", category="water")
    mtn = Biller(name="MTN Mobile", category="mobile")
    syriatel = Biller(name="Syriatel", category="mobile")
    db.add_all([elec, water, mtn, syriatel])
    db.flush()
    db.add_all([
        BillerProduct(biller_id=elec.id, name="Postpaid Bill"),
        BillerProduct(biller_id=water.id, name="Postpaid Bill"),
        BillerProduct(biller_id=mtn.id, name="Prepaid Topup"),
        BillerProduct(biller_id=syriatel.id, name="Prepaid Topup"),
    ])
    db.flush()


@router.get("", response_model=list[BillerOut])
def list_billers(category: str | None = Query(None), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _seed_dev(db)
    q = db.query(Biller)
    if category:
        q = q.filter(Biller.category == category)
    rows = q.order_by(Biller.created_at.desc()).all()
    return [BillerOut(id=str(b.id), name=b.name, category=b.category) for b in rows]
