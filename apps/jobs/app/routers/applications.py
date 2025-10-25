from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Application, User
from ..utils.notify import notify
from ..utils.webhooks import send_webhooks
from ..schemas import ApplicationsListOut, ApplicationOut


router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=ApplicationsListOut)
def my_applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    apps = db.query(Application).filter(Application.user_id == user.id).order_by(Application.created_at.desc()).all()
    return ApplicationsListOut(applications=[
        ApplicationOut(id=str(a.id), job_id=str(a.job_id), user_id=str(a.user_id), status=a.status, cover_letter=a.cover_letter, created_at=a.created_at)
        for a in apps
    ])


@router.post("/{application_id}/withdraw", response_model=ApplicationOut)
def withdraw_application(application_id: str, tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    app = db.get(Application, application_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if app.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your application")
    if app.status in ("accepted", "rejected"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot withdraw finalized application")
    app.status = "withdrawn"
    db.flush()
    try:
        notify("application.withdrawn", {"application_id": str(app.id), "job_id": str(app.job_id), "user_id": str(user.id)})
    except Exception:
        pass
    try:
        send_webhooks(db, "application.withdrawn", {"application_id": str(app.id), "job_id": str(app.job_id), "user_id": str(user.id)}, tasks=tasks)
    except Exception:
        pass
    return ApplicationOut(id=str(app.id), job_id=str(app.job_id), user_id=str(app.user_id), status=app.status, cover_letter=app.cover_letter, created_at=app.created_at)
