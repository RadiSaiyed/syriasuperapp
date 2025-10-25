from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Contact
from ..schemas import AddContactIn, ContactOut


router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("/add")
def add_contact(payload: AddContactIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.phone == payload.phone).one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    if target.id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot add self")
    exists = db.query(Contact).filter(Contact.user_id == user.id, Contact.contact_user_id == target.id).one_or_none()
    if exists is None:
        db.add(Contact(user_id=user.id, contact_user_id=target.id))
        db.flush()
    return {"detail": "ok"}


@router.get("", response_model=list[ContactOut])
def list_contacts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Contact, User).join(User, Contact.contact_user_id == User.id).filter(Contact.user_id == user.id).all()
    out: list[ContactOut] = []
    for c, u in rows:
        out.append(ContactOut(user_id=str(u.id), phone=u.phone, name=u.name))
    return out

