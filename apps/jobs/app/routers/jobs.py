from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from typing import Literal
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Job, Application, Favorite, JobTag
from ..schemas import JobsListOut, JobOut, ApplyIn, ApplicationOut
from ..utils.notify import notify
from ..utils.webhooks import send_webhooks
import os
import httpx


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobsListOut)
def list_open_jobs(
    q: str | None = None,
    location: str | None = None,
    min_salary: int | None = Query(None, ge=0),
    max_salary: int | None = Query(None, ge=0),
    company_id: str | None = None,
    category: str | None = None,
    employment_type: str | None = None,
    remote: bool | None = None,
    tags: list[str] | None = Query(None, description="Filter by tag(s)"),
    tags_mode: Literal["any", "all"] = Query("any", description="Tag match mode"),
    limit: int = Query(20, gt=0, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Job).filter(Job.status == "open")
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Job.title.ilike(like), Job.description.ilike(like)))
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    if min_salary is not None:
        query = query.filter(Job.salary_cents.is_(None) | (Job.salary_cents >= min_salary))
    if max_salary is not None:
        query = query.filter(Job.salary_cents.is_(None) | (Job.salary_cents <= max_salary))
    if company_id:
        query = query.filter(Job.company_id == company_id)
    if category:
        query = query.filter(Job.category == category)
    if employment_type:
        query = query.filter(Job.employment_type == employment_type)
    if remote is not None:
        query = query.filter(Job.is_remote == bool(remote))
    if tags:
        if tags_mode == "all":
            sub = (
                db.query(JobTag.job_id)
                .filter(JobTag.tag.in_(tags))
                .group_by(JobTag.job_id)
                .having(func.count(func.distinct(JobTag.tag)) >= len(set(tags)))
                .subquery()
            )
            query = query.filter(Job.id.in_(sub))
        else:
            sub = db.query(JobTag.job_id).filter(JobTag.tag.in_(tags)).subquery()
            query = query.filter(Job.id.in_(sub))

    total = query.count()
    jobs = query.order_by(Job.created_at.desc()).limit(limit).offset(offset).all()
    next_offset = offset + limit if (offset + limit) < total else None
    job_ids = [j.id for j in jobs]
    tags_map = {jid: [] for jid in job_ids}
    if job_ids:
        for t in db.query(JobTag).filter(JobTag.job_id.in_(job_ids)).all():
            tags_map[t.job_id].append(t.tag)
    return JobsListOut(
        jobs=[
            JobOut(
                id=str(j.id),
                company_id=str(j.company_id),
                title=j.title,
                description=j.description,
                location=j.location,
                salary_cents=j.salary_cents,
                category=j.category,
                employment_type=j.employment_type,
                is_remote=j.is_remote,
                tags=tags_map.get(j.id, []),
                status=j.status,
                created_at=j.created_at,
            )
            for j in jobs
        ],
        total=total,
        next_offset=next_offset,
    )


@router.get("/favorites", response_model=JobsListOut)
def list_favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    favs = db.query(Favorite).filter(Favorite.user_id == user.id).all()
    job_ids = [f.job_id for f in favs]
    if not job_ids:
        return JobsListOut(jobs=[], total=0, next_offset=None)
    jobs = db.query(Job).filter(Job.id.in_(job_ids), Job.status == "open").order_by(Job.created_at.desc()).all()
    tags_map = {jid: [] for jid in job_ids}
    for t in db.query(JobTag).filter(JobTag.job_id.in_(job_ids)).all():
        tags_map[t.job_id].append(t.tag)
    return JobsListOut(
        jobs=[
            JobOut(
                id=str(j.id), company_id=str(j.company_id), title=j.title, description=j.description,
                location=j.location, salary_cents=j.salary_cents, category=j.category, employment_type=j.employment_type, is_remote=j.is_remote,
                tags=tags_map.get(j.id, []), status=j.status, created_at=j.created_at,
            )
            for j in jobs
        ],
        total=len(jobs),
        next_offset=None,
    )


@router.get("/recommendations", response_model=JobsListOut)
def recommended_jobs(
    q: str | None = Query(None, description="User intent or title keywords"),
    limit: int = Query(20, gt=0, le=100),
    db: Session = Depends(get_db),
):
    base = os.getenv("AI_GATEWAY_BASE_URL", "http://localhost:8099")
    jobs = db.query(Job).filter(Job.status == "open").order_by(Job.created_at.desc()).limit(200).all()
    if not q or not jobs:
        tags_map: dict = {}
        if jobs:
            ids = [j.id for j in jobs]
            for t in db.query(JobTag).filter(JobTag.job_id.in_(ids)).all():
                tags_map.setdefault(t.job_id, []).append(t.tag)
        return JobsListOut(
            jobs=[
                JobOut(
                    id=str(j.id), company_id=str(j.company_id), title=j.title, description=j.description,
                    location=j.location, salary_cents=j.salary_cents, category=j.category, employment_type=j.employment_type, is_remote=j.is_remote,
                    tags=tags_map.get(j.id, []), status=j.status, created_at=j.created_at,
                )
                for j in jobs[:limit]
            ],
            total=len(jobs),
            next_offset=None,
        )
    items = [{"id": str(j.id), "text": f"{j.title} {j.location or ''} {j.category or ''}"} for j in jobs]
    scores: list[dict] = []
    try:
        with httpx.Client(base_url=base, timeout=5.0) as client:
            r = client.post("/v1/rank", json={"query": q, "items": items})
            r.raise_for_status()
            scores = r.json().get("scores", [])
    except Exception:
        scores = []
    by_id = {str(j.id): j for j in jobs}
    ordered = []
    for s in scores:
        j = by_id.get(str(s.get("id")))
        if j:
            ordered.append(j)
    if not ordered:
        ordered = jobs
    tags_map: dict = {}
    ids = [j.id for j in ordered[:limit]]
    for t in db.query(JobTag).filter(JobTag.job_id.in_(ids)).all():
        tags_map.setdefault(t.job_id, []).append(t.tag)
    return JobsListOut(
        jobs=[
            JobOut(
                id=str(j.id), company_id=str(j.company_id), title=j.title, description=j.description,
                location=j.location, salary_cents=j.salary_cents, category=j.category, employment_type=j.employment_type, is_remote=j.is_remote,
                tags=tags_map.get(j.id, []), status=j.status, created_at=j.created_at,
            )
            for j in ordered[:limit]
        ],
        total=len(ordered[:limit]),
        next_offset=None,
    )


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    tags = [t.tag for t in db.query(JobTag).filter(JobTag.job_id == j.id).all()]
    return JobOut(
        id=str(j.id), company_id=str(j.company_id), title=j.title, description=j.description,
        location=j.location, salary_cents=j.salary_cents, category=j.category, employment_type=j.employment_type, is_remote=j.is_remote,
        tags=tags, status=j.status, created_at=j.created_at,
    )


@router.post("/{job_id}/apply", response_model=ApplicationOut)
def apply(job_id: str, payload: ApplyIn, tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ("seeker", "employer"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")
    job = db.get(Job, job_id)
    if not job or job.status != "open":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not open")
    existing = db.query(Application).filter(Application.job_id == job.id, Application.user_id == user.id).one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already applied")
    app = Application(job_id=job.id, user_id=user.id, cover_letter=payload.cover_letter, status="applied")
    db.add(app)
    db.flush()
    try:
        notify("application.created", {"job_id": str(job.id), "application_id": str(app.id), "user_id": str(user.id)})
    except Exception:
        pass
    try:
        send_webhooks(db, "application.created", {"job_id": str(job.id), "application_id": str(app.id), "user_id": str(user.id)}, tasks=tasks)
    except Exception:
        pass
    return ApplicationOut(id=str(app.id), job_id=str(app.job_id), user_id=str(app.user_id), status=app.status, cover_letter=app.cover_letter, created_at=app.created_at)


@router.post("/{job_id}/favorite")
def favorite_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job or job.status != "open":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not open")
    existing = db.query(Favorite).filter(Favorite.job_id == job.id, Favorite.user_id == user.id).one_or_none()
    if existing:
        return {"detail": "already_favorited"}
    fav = Favorite(job_id=job.id, user_id=user.id)
    db.add(fav)
    db.flush()
    return {"detail": "ok"}


@router.delete("/{job_id}/favorite")
def unfavorite_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    existing = db.query(Favorite).filter(Favorite.job_id == job.id, Favorite.user_id == user.id).one_or_none()
    if not existing:
        return {"detail": "not_favorited"}
    db.delete(existing)
    return {"detail": "ok"}


 
