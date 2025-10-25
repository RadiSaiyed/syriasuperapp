from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Company, Job, Application, JobTag
from ..schemas import (
    CompanyCreateIn,
    CompanyOut,
    JobCreateIn,
    JobOut,
    ApplicationsListOut,
    ApplicationOut,
    JobUpdateIn,
    ApplicationStatusUpdateIn,
)
from ..utils.notify import notify
from ..utils.webhooks import send_webhooks


router = APIRouter(prefix="/employer", tags=["employer"])


@router.post("/company", response_model=CompanyOut)
def create_company(payload: CompanyCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ("employer", "seeker"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")
    existing = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Company already exists")
    company = Company(owner_user_id=user.id, name=payload.name, description=payload.description)
    user.role = "employer"
    db.add(company)
    db.flush()
    return CompanyOut(id=str(company.id), name=company.name, description=company.description)


@router.get("/company", response_model=CompanyOut)
def get_my_company(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No company")
    return CompanyOut(id=str(company.id), name=company.name, description=company.description)


@router.post("/jobs", response_model=JobOut)
def create_job(payload: JobCreateIn, tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "employer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an employer")
    company = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Create company first")
    job = Job(
        company_id=company.id,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        salary_cents=payload.salary_cents,
        category=payload.category,
        employment_type=payload.employment_type,
        is_remote=bool(payload.is_remote) if payload.is_remote is not None else False,
        status="open",
    )
    db.add(job)
    db.flush()
    try:
        notify("job.created", {"job_id": str(job.id), "company_id": str(company.id)})
    except Exception:
        pass
    try:
        send_webhooks(db, "job.created", {"job_id": str(job.id), "company_id": str(company.id)}, tasks=tasks)
    except Exception:
        pass
    if payload.tags:
        for t in payload.tags:
            if t:
                db.add(JobTag(job_id=job.id, tag=t.strip()[:32]))
    return JobOut(
        id=str(job.id), company_id=str(job.company_id), title=job.title, description=job.description,
        location=job.location, salary_cents=job.salary_cents,
        category=job.category, employment_type=job.employment_type, is_remote=job.is_remote, tags=[t.tag for t in db.query(JobTag).filter(JobTag.job_id==job.id).all()],
        status=job.status, created_at=job.created_at,
    )


@router.get("/jobs", response_model=list[JobOut])
def my_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "employer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an employer")
    company = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not company:
        return []
    jobs = (
        db.query(Job).filter(Job.company_id == company.id).order_by(Job.created_at.desc()).all()
    )
    job_ids = [j.id for j in jobs]
    tags_map = {jid: [] for jid in job_ids}
    if job_ids:
        for t in db.query(JobTag).filter(JobTag.job_id.in_(job_ids)).all():
            tags_map[t.job_id].append(t.tag)
    return [
        JobOut(
            id=str(j.id), company_id=str(j.company_id), title=j.title, description=j.description,
            location=j.location, salary_cents=j.salary_cents, category=j.category, employment_type=j.employment_type, is_remote=j.is_remote,
            tags=tags_map.get(j.id, []), status=j.status, created_at=j.created_at,
        )
        for j in jobs
    ]


@router.get("/jobs/{job_id}/applications", response_model=ApplicationsListOut)
def job_applications(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "employer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an employer")
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    company = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not company or company.id != job.company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your job")

    apps = db.query(Application).filter(Application.job_id == job.id).order_by(Application.created_at.desc()).all()
    return ApplicationsListOut(applications=[
        ApplicationOut(id=str(a.id), job_id=str(a.job_id), user_id=str(a.user_id), status=a.status, cover_letter=a.cover_letter, created_at=a.created_at)
        for a in apps
    ])


@router.patch("/jobs/{job_id}", response_model=JobOut)
def update_job(job_id: str, payload: JobUpdateIn, tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "employer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an employer")
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    company = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not company or company.id != job.company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your job")
    if payload.title is not None:
        job.title = payload.title
    if payload.description is not None:
        job.description = payload.description
    if payload.location is not None:
        job.location = payload.location
    if payload.salary_cents is not None:
        job.salary_cents = payload.salary_cents
    if payload.status is not None:
        if payload.status not in ("open", "closed"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
        job.status = payload.status
    if payload.category is not None:
        job.category = payload.category
    if payload.employment_type is not None:
        job.employment_type = payload.employment_type
    if payload.is_remote is not None:
        job.is_remote = bool(payload.is_remote)
    if payload.tags is not None:
        # Replace tags with provided list
        db.query(JobTag).filter(JobTag.job_id == job.id).delete()
        for t in payload.tags:
            if t:
                db.add(JobTag(job_id=job.id, tag=t.strip()[:32]))
    db.flush()
    try:
        notify("job.updated", {"job_id": str(job.id)})
    except Exception:
        pass
    try:
        send_webhooks(db, "job.updated", {"job_id": str(job.id)}, tasks=tasks)
    except Exception:
        pass
    return JobOut(
        id=str(job.id), company_id=str(job.company_id), title=job.title, description=job.description,
        location=job.location, salary_cents=job.salary_cents, category=job.category, employment_type=job.employment_type, is_remote=job.is_remote,
        tags=[t.tag for t in db.query(JobTag).filter(JobTag.job_id==job.id).all()], status=job.status, created_at=job.created_at,
    )


@router.patch("/applications/{application_id}", response_model=ApplicationOut)
def update_application_status(
    application_id: str,
    payload: ApplicationStatusUpdateIn,
    tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "employer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an employer")
    app = db.get(Application, application_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    job = db.get(Job, app.job_id)
    company = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not job or not company or job.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your job")
    if payload.status not in ("applied", "reviewed", "accepted", "rejected"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
    app.status = payload.status
    db.flush()
    try:
        notify("application.status_changed", {"application_id": str(app.id), "job_id": str(job.id), "status": app.status})
    except Exception:
        pass
    try:
        send_webhooks(db, "application.status_changed", {"application_id": str(app.id), "job_id": str(job.id), "status": app.status}, tasks=tasks)
    except Exception:
        pass
    return ApplicationOut(
        id=str(app.id), job_id=str(app.job_id), user_id=str(app.user_id), status=app.status, cover_letter=app.cover_letter, created_at=app.created_at
    )
