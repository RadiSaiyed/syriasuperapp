from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Farm, Job, Application
from ..schemas import JobsListOut, JobOut, ApplyIn, ApplicationOut, ApplicationsListOut
from ..utils import notify


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobsListOut)
def browse_jobs(
    q: str | None = None,
    farm_id: str | None = None,
    location: str | None = None,
    limit: int = Query(20, gt=0, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Job).filter(Job.status == "open")
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Job.title.ilike(like), Job.description.ilike(like)))
    if farm_id:
        query = query.filter(Job.farm_id == farm_id)
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    total = query.count()
    rows = query.order_by(Job.created_at.desc()).limit(limit).offset(offset).all()
    return JobsListOut(jobs=[
        JobOut(id=str(j.id), farm_id=str(j.farm_id), title=j.title, description=j.description, location=j.location,
               wage_per_day_cents=j.wage_per_day_cents, start_date=j.start_date, end_date=j.end_date,
               status=j.status, created_at=j.created_at)
        for j in rows
    ], total=total)


@router.get("/{job_id}", response_model=JobOut)
def job_details(job_id: str, db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobOut(id=str(j.id), farm_id=str(j.farm_id), title=j.title, description=j.description, location=j.location,
                  wage_per_day_cents=j.wage_per_day_cents, start_date=j.start_date, end_date=j.end_date,
                  status=j.status, created_at=j.created_at)


@router.post("/{job_id}/apply", response_model=ApplicationOut)
def apply(job_id: str, payload: ApplyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if not j or j.status != "open":
        raise HTTPException(status_code=404, detail="Job not open")
    a = Application(job_id=j.id, user_id=user.id, message=payload.message or None)
    db.add(a)
    db.flush()
    notify("application.created", {"application_id": str(a.id), "job_id": str(j.id)})
    return ApplicationOut(id=str(a.id), job_id=str(a.job_id), user_id=str(a.user_id), message=a.message, status=a.status, created_at=a.created_at)


@router.get("/my_applications", response_model=ApplicationsListOut)
def my_applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Application).filter(Application.user_id == user.id).order_by(Application.created_at.desc()).all()
    return ApplicationsListOut(applications=[
        ApplicationOut(id=str(a.id), job_id=str(a.job_id), user_id=str(a.user_id), message=a.message, status=a.status, created_at=a.created_at)
        for a in rows
    ])


@router.post("/my_applications/{application_id}/withdraw", response_model=ApplicationOut)
def withdraw(application_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(Application, application_id)
    if not a or a.user_id != user.id:
        raise HTTPException(status_code=404, detail="Application not found")
    if a.status in ("accepted", "rejected"):
        raise HTTPException(status_code=400, detail="Cannot withdraw finalized application")
    a.status = "withdrawn"
    db.flush()
    notify("application.withdrawn", {"application_id": str(a.id)})
    return ApplicationOut(id=str(a.id), job_id=str(a.job_id), user_id=str(a.user_id), message=a.message, status=a.status, created_at=a.created_at)
