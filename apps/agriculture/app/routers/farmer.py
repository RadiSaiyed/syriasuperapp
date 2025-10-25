from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Farm, Listing, Job, Application, Order
from ..schemas import (
    FarmCreateIn,
    FarmOut,
    ListingCreateIn,
    ListingUpdateIn,
    ListingOut,
    JobCreateIn,
    JobOut,
    ApplicationsListOut,
    ApplicationOut,
    ApplicationStatusUpdateIn,
    OrdersListOut,
    OrderOut,
)
from ..utils import notify


router = APIRouter(prefix="/farmer", tags=["farmer"])


def _require_farmer(user: User):
    if user.role not in ("farmer",):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Farmer role required")


@router.post("/farm", response_model=FarmOut)
def create_farm(payload: FarmCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_farmer(user)
    existing = db.query(Farm).filter(Farm.owner_user_id == user.id).one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Farm already exists")
    f = Farm(owner_user_id=user.id, name=payload.name, location=payload.location, description=payload.description)
    db.add(f)
    db.flush()
    notify("farm.created", {"farm_id": str(f.id), "owner_user_id": str(user.id)})
    return FarmOut(id=str(f.id), name=f.name, location=f.location, description=f.description, created_at=f.created_at)


@router.get("/farm", response_model=FarmOut)
def get_farm(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_farmer(user)
    f = db.query(Farm).filter(Farm.owner_user_id == user.id).one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Farm not found")
    return FarmOut(id=str(f.id), name=f.name, location=f.location, description=f.description, created_at=f.created_at)


@router.post("/listings", response_model=ListingOut)
def create_listing(payload: ListingCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_farmer(user)
    f = db.query(Farm).filter(Farm.owner_user_id == user.id).one_or_none()
    if not f:
        raise HTTPException(status_code=400, detail="Farm required")
    l = Listing(
        farm_id=f.id,
        produce_name=payload.produce_name,
        category=payload.category,
        quantity_kg=payload.quantity_kg,
        price_per_kg_cents=payload.price_per_kg_cents,
    )
    db.add(l)
    db.flush()
    notify("listing.created", {"listing_id": str(l.id), "farm_id": str(f.id)})
    return ListingOut(
        id=str(l.id), farm_id=str(l.farm_id), produce_name=l.produce_name, category=l.category,
        quantity_kg=l.quantity_kg, price_per_kg_cents=l.price_per_kg_cents, status=l.status, created_at=l.created_at,
    )


@router.get("/listings", response_model=list[ListingOut])
def list_my_listings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_farmer(user)
    f = db.query(Farm).filter(Farm.owner_user_id == user.id).one_or_none()
    if not f:
        return []
    rows = db.query(Listing).filter(Listing.farm_id == f.id).order_by(Listing.created_at.desc()).all()
    return [
        ListingOut(
            id=str(l.id), farm_id=str(l.farm_id), produce_name=l.produce_name, category=l.category,
            quantity_kg=l.quantity_kg, price_per_kg_cents=l.price_per_kg_cents, status=l.status, created_at=l.created_at,
        )
        for l in rows
    ]


@router.patch("/listings/{listing_id}", response_model=ListingOut)
def update_listing(listing_id: str, payload: ListingUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_farmer(user)
    l = db.get(Listing, listing_id)
    if not l:
        raise HTTPException(status_code=404, detail="Listing not found")
    f = db.query(Farm).filter(Farm.owner_user_id == user.id).one_or_none()
    if not f or l.farm_id != f.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if payload.quantity_kg is not None:
        l.quantity_kg = payload.quantity_kg
    if payload.price_per_kg_cents is not None:
        l.price_per_kg_cents = payload.price_per_kg_cents
    if payload.status is not None:
        l.status = payload.status
    db.flush()
    notify("listing.updated", {"listing_id": str(l.id)})
    return ListingOut(
        id=str(l.id), farm_id=str(l.farm_id), produce_name=l.produce_name, category=l.category,
        quantity_kg=l.quantity_kg, price_per_kg_cents=l.price_per_kg_cents, status=l.status, created_at=l.created_at,
    )


@router.post("/jobs", response_model=JobOut)
def create_job(payload: JobCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_farmer(user)
    f = db.query(Farm).filter(Farm.owner_user_id == user.id).one_or_none()
    if not f:
        raise HTTPException(status_code=400, detail="Farm required")
    j = Job(
        farm_id=f.id,
        title=payload.title,
        description=payload.description,
        location=payload.location or f.location,
        wage_per_day_cents=payload.wage_per_day_cents,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(j)
    db.flush()
    notify("job.created", {"job_id": str(j.id), "farm_id": str(f.id)})
    return JobOut(
        id=str(j.id), farm_id=str(j.farm_id), title=j.title, description=j.description, location=j.location,
        wage_per_day_cents=j.wage_per_day_cents, start_date=j.start_date, end_date=j.end_date,
        status=j.status, created_at=j.created_at,
    )


@router.get("/jobs", response_model=list[JobOut])
def list_my_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_farmer(user)
    f = db.query(Farm).filter(Farm.owner_user_id == user.id).one_or_none()
    if not f:
        return []
    rows = db.query(Job).filter(Job.farm_id == f.id).order_by(Job.created_at.desc()).all()
    return [
        JobOut(
            id=str(j.id), farm_id=str(j.farm_id), title=j.title, description=j.description, location=j.location,
            wage_per_day_cents=j.wage_per_day_cents, start_date=j.start_date, end_date=j.end_date,
            status=j.status, created_at=j.created_at,
        )
        for j in rows
    ]


@router.get("/jobs/{job_id}/applications", response_model=ApplicationsListOut)
def list_applications(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_farmer(user)
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    f = db.query(Farm).filter(Farm.owner_user_id == user.id).one_or_none()
    if not f or j.farm_id != f.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    apps = db.query(Application).filter(Application.job_id == j.id).order_by(Application.created_at.desc()).all()
    return ApplicationsListOut(applications=[
        ApplicationOut(id=str(a.id), job_id=str(a.job_id), user_id=str(a.user_id), message=a.message, status=a.status, created_at=a.created_at)
        for a in apps
    ])


@router.patch("/applications/{application_id}", response_model=ApplicationOut)
def update_application(application_id: str, payload: ApplicationStatusUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_farmer(user)
    a = db.get(Application, application_id)
    if not a:
        raise HTTPException(status_code=404, detail="Application not found")
    j = db.get(Job, a.job_id)
    f = db.query(Farm).filter(Farm.owner_user_id == user.id).one_or_none()
    if not j or not f or j.farm_id != f.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    a.status = payload.status
    db.flush()
    notify("application.status_changed", {"application_id": str(a.id), "status": a.status})
    return ApplicationOut(id=str(a.id), job_id=str(a.job_id), user_id=str(a.user_id), message=a.message, status=a.status, created_at=a.created_at)


@router.get("/orders", response_model=OrdersListOut)
def list_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_farmer(user)
    f = db.query(Farm).filter(Farm.owner_user_id == user.id).one_or_none()
    if not f:
        return OrdersListOut(orders=[])
    # Orders of my listings
    listing_ids = [l.id for l in db.query(Listing).filter(Listing.farm_id == f.id).all()]
    if not listing_ids:
        return OrdersListOut(orders=[])
    orders = db.query(Order).filter(Order.listing_id.in_(listing_ids)).order_by(Order.created_at.desc()).all()
    return OrdersListOut(orders=[
        OrderOut(id=str(o.id), listing_id=str(o.listing_id), qty_kg=o.qty_kg, total_cents=o.total_cents, status=o.status, created_at=o.created_at)
        for o in orders
    ])

