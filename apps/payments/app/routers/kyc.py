from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import User


router = APIRouter(prefix="/kyc", tags=["kyc"])


@router.get("")
def get_kyc(user: User = Depends(get_current_user)):
    return {
        "kyc_level": user.kyc_level,
        "kyc_status": user.kyc_status,
    }


@router.post("/submit")
def submit_kyc(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.kyc_status == "approved":
        return {"detail": "already approved"}
    user.kyc_status = "pending"
    db.flush()
    return {"detail": "submitted"}


@router.post("/dev/approve")
def dev_approve(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.kyc_level = 1
    user.kyc_status = "approved"
    db.flush()
    return {"detail": "approved", "kyc_level": user.kyc_level}

