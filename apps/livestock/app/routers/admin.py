from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Ranch, AnimalListing, ProductListing


router = APIRouter(prefix="/admin", tags=["admin"]) 


@router.post("/seed")
def seed(db: Session = Depends(get_db)):
    if db.query(ProductListing).count() > 0 or db.query(AnimalListing).count() > 0:
        db.query(AnimalListing).update({AnimalListing.status: "available"})
        db.query(ProductListing).update({ProductListing.status: "active"})
        db.flush()
        return {"detail": "reset"}
    # Sellers + ranches
    sellers = []
    for i in range(2):
        u = User(phone=f"+96390000031{i}", name=f"Seller {i+1}", role="seller")
        db.add(u)
        db.flush()
        r = Ranch(owner_user_id=u.id, name=f"Ranch {i+1}", location=["Hama", "Homs"][i], description="Demo ranch")
        db.add(r)
        db.flush()
        sellers.append((u, r))
    # Animals
    for _, r in sellers:
        rows = [
            ("cow", "Holstein", "F", 24, 450, 1500000),
            ("sheep", "Awassi", "F", 12, 60, 350000),
        ]
        for species, breed, sex, age, weight, price in rows:
            a = AnimalListing(ranch_id=r.id, species=species, breed=breed, sex=sex, age_months=age, weight_kg=weight, price_cents=price)
            db.add(a)
    # Products
    for _, r in sellers:
        items = [
            ("milk", "liter", 200, 700),
            ("eggs", "dozen", 50, 2500),
            ("cheese", "kg", 30, 12000),
        ]
        for typ, unit, qty, price in items:
            p = ProductListing(ranch_id=r.id, product_type=typ, unit=unit, quantity=qty, price_per_unit_cents=price)
            db.add(p)
    # Buyer seed
    b = User(phone="+963900000400", name="Buyer B", role="buyer")
    db.add(b)
    return {"detail": "seeded"}
