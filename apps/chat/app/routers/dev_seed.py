from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..config import settings


router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/seed")
def seed_dev(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Best-effort dev seeding.
    - Ensures the authenticated user exists (get_current_user already auto-provisions on JWKS tokens).
    - No-op otherwise; returns a simple OK so that E2E flows can depend on a 200 in dev.
    """
    if settings.ENV.lower() != "dev":
        return {"detail": "noop (not dev)"}
    # Touch the user to update last_seen in the future if needed; currently just return OK.
    return {"detail": "ok", "user": str(user.id)}

