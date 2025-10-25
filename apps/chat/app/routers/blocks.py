from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Block, User


router = APIRouter(prefix="/blocks", tags=["blocks"])


@router.post("")
def block_user(blocked_user_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if str(user.id) == blocked_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot block self")
    u = db.get(User, blocked_user_id)
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    b = db.query(Block).filter(Block.user_id == user.id, Block.blocked_user_id == u.id).one_or_none()
    if b is None:
        b = Block(user_id=user.id, blocked_user_id=u.id)
        db.add(b)
    return {"detail": "ok"}


@router.delete("")
def unblock_user(blocked_user_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.query(Block).filter(Block.user_id == user.id, Block.blocked_user_id == blocked_user_id).one_or_none()
    if b:
        db.delete(b)
    return {"detail": "ok"}


@router.get("")
def list_blocks(user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Block).filter(Block.user_id == user.id).all()
    return [{"blocked_user_id": str(x.blocked_user_id), "created_at": x.created_at.isoformat()} for x in rows]

