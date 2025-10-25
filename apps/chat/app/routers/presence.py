from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import PresenceOut


router = APIRouter(prefix="/presence", tags=["presence"])


@router.get("/{user_id}", response_model=PresenceOut)
def get_presence(user_id: str, db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        return PresenceOut(user_id=user_id, online=False, last_seen=None)
    # Online if WS connection exists (checked via ws module registry)
    try:
        from ..ws import connections
        online = bool(connections.get(str(user_id)))
    except Exception:
        online = False
    return PresenceOut(user_id=str(user_id), online=online, last_seen=u.last_seen)


@router.post("/ping", response_model=PresenceOut)
def ping(user=Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.get(User, user.id)
    if u:
        u.last_seen = datetime.utcnow()
    return get_presence(str(user.id), db)

