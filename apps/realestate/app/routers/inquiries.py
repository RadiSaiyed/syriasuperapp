from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Inquiry, Listing
from ..auth import get_current_user
from ..schemas import InquiryCreateIn, InquiriesListOut, InquiryOut


router = APIRouter(prefix="/inquiries", tags=["inquiries"])


@router.get("", response_model=InquiriesListOut)
def list_inquiries(user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Inquiry).filter(Inquiry.user_id == user.id).order_by(Inquiry.created_at.desc()).limit(100).all()
    return InquiriesListOut(items=[InquiryOut(id=str(i.id), listing_id=str(i.listing_id), message=i.message or None) for i in rows])


@router.post("", response_model=InquiryOut)
def create_inquiry(payload: InquiryCreateIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, payload.listing_id)
    if l is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    i = Inquiry(user_id=user.id, listing_id=l.id, message=payload.message or None)
    db.add(i)
    db.flush()
    return InquiryOut(id=str(i.id), listing_id=str(i.listing_id), message=i.message or None)

