from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Company, Vehicle


router = APIRouter(prefix="/admin", tags=["admin"]) 


@router.post("/seed")
def seed(db: Session = Depends(get_db)):
    if db.query(Vehicle).count() > 0:
        return {"detail": "exists"}
    # Create two sellers + companies
    sellers = []
    for i in range(2):
        u = User(phone=f"+9639000005{i}0", name=f"RentCo {i+1}", role="seller")
        db.add(u)
        db.flush()
        c = Company(owner_user_id=u.id, name=f"RentCo {i+1}", location=["Damascus", "Aleppo"][i], description="Demo rental company")
        db.add(c)
        db.flush()
        sellers.append((u, c))
    # Vehicles
    data = [
        ("Toyota", "Corolla", 2018, "auto", 5, "Damascus", 25000),
        ("Hyundai", "Elantra", 2019, "auto", 5, "Damascus", 28000),
        ("Kia", "Sportage", 2020, "auto", 5, "Aleppo", 35000),
        ("Renault", "Logan", 2017, "manual", 5, "Aleppo", 18000),
    ]
    for idx, (make, model, year, trans, seats, loc, price) in enumerate(data):
        c = sellers[idx % len(sellers)][1]
        v = Vehicle(company_id=c.id, make=make, model=model, year=year, transmission=trans, seats=seats, location=loc, price_per_day_cents=price)
        db.add(v)
    # A renter
    r = User(phone="+963900000599", name="Renter A", role="renter")
    db.add(r)
    return {"detail": "seeded"}

