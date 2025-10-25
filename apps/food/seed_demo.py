"""
Seed demo data for Food API (dev only).

Creates:
- Demo users (owners and customers)
- 3 restaurants across Damascus, Aleppo, Latakia
- Menu items for each restaurant
- Sample images, favorites, and reviews

Usage (from repo root):
  DB_URL=postgresql+psycopg2://postgres:postgres@localhost:5443/food \
  python apps/food/seed_demo.py
"""
from __future__ import annotations

import os
from sqlalchemy import text

try:
    # When PYTHONPATH=apps/food
    from app.database import SessionLocal
    from app.models import (
        Base,
        User,
        Restaurant,
        MenuItem,
        RestaurantImage,
        FavoriteRestaurant,
        RestaurantReview,
    )
except ModuleNotFoundError:
    # Fallback when importing from repo root
    from apps.food.app.database import SessionLocal  # type: ignore
    from apps.food.app.models import (  # type: ignore
        Base,
        User,
        Restaurant,
        MenuItem,
        RestaurantImage,
        FavoriteRestaurant,
        RestaurantReview,
    )
else:
    # Ensure Base import when imported via app.*
    from app.models import Base  # type: ignore


def ensure_user(session, phone: str, name: str) -> User:
    u = session.query(User).filter(User.phone == phone).one_or_none()
    if u:
        if not u.name:
            u.name = name
        session.flush()
        return u
    u = User(phone=phone, name=name)
    session.add(u)
    session.flush()
    return u


def ensure_restaurant(session, owner: User | None, name: str, city: str, description: str, address: str | None = None) -> Restaurant:
    r = (
        session.query(Restaurant)
        .filter(Restaurant.name == name, Restaurant.city == city)
        .one_or_none()
    )
    if r:
        # Update owner/address/description if missing
        if owner and r.owner_user_id != owner.id:
            r.owner_user_id = owner.id
        if address and not r.address:
            r.address = address
        if description and not r.description:
            r.description = description
        session.flush()
        return r
    r = Restaurant(
        owner_user_id=(owner.id if owner else None),
        name=name,
        city=city,
        description=description,
        address=address,
    )
    session.add(r)
    session.flush()
    return r


def ensure_menu_item(session, r: Restaurant, name: str, price_cents: int, description: str | None = None) -> MenuItem:
    mi = (
        session.query(MenuItem)
        .filter(MenuItem.restaurant_id == r.id, MenuItem.name == name)
        .one_or_none()
    )
    if mi:
        # Update price/desc if changed
        changed = False
        if description is not None and mi.description != description:
            mi.description = description
            changed = True
        if price_cents is not None and mi.price_cents != price_cents:
            mi.price_cents = price_cents
            changed = True
        if changed:
            session.flush()
        return mi
    mi = MenuItem(restaurant_id=r.id, name=name, description=description, price_cents=price_cents, available=True)
    session.add(mi)
    session.flush()
    return mi


def ensure_image(session, r: Restaurant, url: str, sort: int = 0):
    exists = (
        session.query(RestaurantImage)
        .filter(RestaurantImage.restaurant_id == r.id, RestaurantImage.url == url)
        .one_or_none()
    )
    if not exists:
        session.add(RestaurantImage(restaurant_id=r.id, url=url, sort_order=sort))
        session.flush()


def ensure_favorite(session, user: User, r: Restaurant):
    exists = (
        session.query(FavoriteRestaurant)
        .filter(FavoriteRestaurant.user_id == user.id, FavoriteRestaurant.restaurant_id == r.id)
        .one_or_none()
    )
    if not exists:
        session.add(FavoriteRestaurant(user_id=user.id, restaurant_id=r.id))
        session.flush()


def add_review(session, r: Restaurant, user: User, rating: int, comment: str | None = None):
    exists = (
        session.query(RestaurantReview)
        .filter(RestaurantReview.restaurant_id == r.id, RestaurantReview.user_id == user.id)
        .one_or_none()
    )
    if not exists:
        session.add(RestaurantReview(restaurant_id=r.id, user_id=user.id, rating=rating, comment=comment))
        session.flush()


def main():
    print("Seeding demo data for Food…")
    with SessionLocal() as session:
        # Create tables if missing
        try:
            Base.metadata.create_all(bind=session.bind)
        except Exception:
            pass
        # Best-effort: add columns if DB created from older schema
        try:
            session.execute(text("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS address VARCHAR(256)"))
            session.execute(text("ALTER TABLE restaurant_images ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0"))
            session.commit()
        except Exception:
            session.rollback()

        # Users
        owner1 = ensure_user(session, "+963900000301", "Owner A")
        owner2 = ensure_user(session, "+963900000302", "Owner B")
        alice = ensure_user(session, "+963900000401", "Alice")
        bob = ensure_user(session, "+963900000402", "Bob")

        # Restaurants
        r1 = ensure_restaurant(
            session,
            owner1,
            name="Damascus Eats",
            city="Damascus",
            description="Local favorites",
            address="Main St 1, Damascus",
        )
        ensure_menu_item(session, r1, name="Shawarma", price_cents=15000, description="Chicken shawarma wrap")
        ensure_menu_item(session, r1, name="Falafel", price_cents=8000, description="Crispy falafel")
        ensure_image(session, r1, "https://images.unsplash.com/photo-1604908553980-618a0fd0b041?w=1200", 0)
        ensure_image(session, r1, "https://images.unsplash.com/photo-1608755721190-2c0cb3220a22?w=1200", 1)

        r2 = ensure_restaurant(
            session,
            owner2,
            name="Aleppo Grill",
            city="Aleppo",
            description="Grilled goodness",
            address="Citadel Rd 10, Aleppo",
        )
        ensure_menu_item(session, r2, name="Kebab Plate", price_cents=22000, description="Mixed kebabs")
        ensure_menu_item(session, r2, name="Hummus", price_cents=7000, description="With olive oil")
        ensure_image(session, r2, "https://images.unsplash.com/photo-1550547660-d9450f859349?w=1200", 0)

        r3 = ensure_restaurant(
            session,
            owner2,
            name="Latakia Seafood",
            city="Latakia",
            description="Fresh from the sea",
            address="Seaside Ave 5, Latakia",
        )
        ensure_menu_item(session, r3, name="Grilled Fish", price_cents=35000, description="Daily catch")
        ensure_menu_item(session, r3, name="Shrimp Plate", price_cents=42000, description="Garlic butter")
        ensure_image(session, r3, "https://images.unsplash.com/photo-1544025162-d76694265947?w=1200", 0)

        # Extra demo restaurants (for richer catalog like Lieferando)
        r4 = ensure_restaurant(
            session,
            owner1,
            name="Pizza Palace",
            city="Damascus",
            description="Stone-oven pizza & more",
            address="Old City 12, Damascus",
        )
        ensure_menu_item(session, r4, name="Margherita", price_cents=18000, description="Tomato, mozzarella, basil")
        ensure_menu_item(session, r4, name="Pepperoni", price_cents=22000, description="Beef pepperoni")
        ensure_image(session, r4, "https://images.unsplash.com/photo-1548366086-7a5b0a6cc81b?w=1200", 0)
        ensure_image(session, r4, "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=1200", 1)

        r5 = ensure_restaurant(
            session,
            owner1,
            name="Sushi House",
            city="Damascus",
            description="Fresh sushi & rolls",
            address="River Rd 3, Damascus",
        )
        ensure_menu_item(session, r5, name="California Roll", price_cents=26000, description="Crab, avocado, cucumber")
        ensure_menu_item(session, r5, name="Salmon Nigiri", price_cents=30000, description="2 pcs")
        ensure_image(session, r5, "https://images.unsplash.com/photo-1553621042-f6e147245754?w=1200", 0)

        r6 = ensure_restaurant(
            session,
            owner2,
            name="Burger Factory",
            city="Aleppo",
            description="Gourmet burgers",
            address="Market St 22, Aleppo",
        )
        ensure_menu_item(session, r6, name="Classic Burger", price_cents=20000, description="150g patty, cheese")
        ensure_menu_item(session, r6, name="BBQ Bacon Burger", price_cents=26000, description="Smoky BBQ sauce")
        ensure_image(session, r6, "https://images.unsplash.com/photo-1550547660-3a47de1edb6f?w=1200", 0)

        # Favorites
        ensure_favorite(session, alice, r1)
        ensure_favorite(session, alice, r3)
        ensure_favorite(session, bob, r2)

        # Reviews
        add_review(session, r1, alice, rating=5, comment="Great taste and quick service!")
        add_review(session, r2, bob, rating=4, comment="Tasty kebabs, will order again.")
        add_review(session, r4, alice, rating=5, comment="Crispy crusts, fast delivery.")
        add_review(session, r5, bob, rating=4, comment="Fresh fish, nice variety.")

        session.commit()
    print("Done.")


if __name__ == "__main__":
    # Respect external DB_URL via env for SessionLocal
    if not os.getenv("DB_URL"):
        os.environ["DB_URL"] = "postgresql+psycopg2://postgres:postgres@localhost:5443/food"
    main()
