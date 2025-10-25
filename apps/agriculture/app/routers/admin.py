from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Farm, Listing, Job


router = APIRouter(prefix="/admin", tags=["admin"]) 


@router.post("/seed")
def seed(db: Session = Depends(get_db)):
    # Idempotent seed: if any listings exist, assume seeded
    if db.query(Listing).count() > 0:
        return {"detail": "exists"}

    # Create demo farmers
    farmers = []
    for i in range(2):
        u = User(phone=f"+96390000020{i}", name=f"Farmer {i+1}", role="farmer")
        db.add(u)
        db.flush()
        f = Farm(owner_user_id=u.id, name=f"Farm {i+1}", location=["Damascus", "Hama"][i], description="Demo farm")
        db.add(f)
        db.flush()
        farmers.append((u, f))

    # Create listings
    for fidx, (u, f) in enumerate(farmers):
        items = [
            ("Tomatoes", "vegetable", 120, 1500),
            ("Apples", "fruit", 80, 2500),
        ]
        for name, cat, qty, price in items:
            l = Listing(farm_id=f.id, produce_name=name, category=cat, quantity_kg=qty + fidx * 20, price_per_kg_cents=price)
            db.add(l)
    # Create seasonal jobs
    for u, f in farmers:
        j = Job(farm_id=f.id, title="Harvest Helper", description="Assist with harvest", location=f.location, wage_per_day_cents=8000)
        db.add(j)

    # Create a buyer
    b = User(phone="+963900000300", name="Buyer A", role="buyer")
    db.add(b)
    return {"detail": "seeded"}

