import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


def default_uuid():
    return uuid.uuid4()


class User(Base):
    __tablename__ = "livestock_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    phone = Column(String(32), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=True)
    role = Column(String(24), nullable=False, default="buyer")  # buyer|seller
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    ranch = relationship("Ranch", back_populates="owner", uselist=False)
    orders = relationship("Order", back_populates="buyer")


class Ranch(Base):
    __tablename__ = "livestock_ranches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("livestock_users.id"), nullable=False, unique=True)
    name = Column(String(128), nullable=False)
    location = Column(String(128), nullable=True)
    description = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="ranch")
    animals = relationship("AnimalListing", back_populates="ranch")
    products = relationship("ProductListing", back_populates="ranch")


class AnimalListing(Base):
    __tablename__ = "livestock_animals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    ranch_id = Column(UUID(as_uuid=True), ForeignKey("livestock_ranches.id"), nullable=False)
    species = Column(String(32), nullable=False)  # cow, sheep, goat, chicken, etc.
    breed = Column(String(64), nullable=True)
    sex = Column(String(8), nullable=True)  # M|F
    age_months = Column(Integer, nullable=True)
    weight_kg = Column(Integer, nullable=True)
    price_cents = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="available")  # available|sold|auction
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    ranch = relationship("Ranch", back_populates="animals")


class ProductListing(Base):
    __tablename__ = "livestock_products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    ranch_id = Column(UUID(as_uuid=True), ForeignKey("livestock_ranches.id"), nullable=False)
    product_type = Column(String(32), nullable=False)  # milk, eggs, cheese, meat
    unit = Column(String(16), nullable=False, default="kg")  # kg, liter, dozen
    quantity = Column(Integer, nullable=False)
    price_per_unit_cents = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="active")  # active|sold_out
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    ranch = relationship("Ranch", back_populates="products")


class Order(Base):
    __tablename__ = "livestock_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    buyer_user_id = Column(UUID(as_uuid=True), ForeignKey("livestock_users.id"), nullable=False)
    type = Column(String(16), nullable=False)  # product|animal
    product_id = Column(UUID(as_uuid=True), ForeignKey("livestock_products.id"), nullable=True)
    animal_id = Column(UUID(as_uuid=True), ForeignKey("livestock_animals.id"), nullable=True)
    qty = Column(Integer, nullable=False, default=1)
    total_cents = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="created")  # created|confirmed|canceled
    payment_request_id = Column(String(64), nullable=True)
    payment_transfer_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    buyer = relationship("User", back_populates="orders")


class FavoriteAnimal(Base):
    __tablename__ = "livestock_fav_animals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("livestock_users.id"), nullable=False)
    animal_id = Column(UUID(as_uuid=True), ForeignKey("livestock_animals.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class FavoriteProduct(Base):
    __tablename__ = "livestock_fav_products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("livestock_users.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("livestock_products.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AnimalAuction(Base):
    __tablename__ = "livestock_auctions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    animal_id = Column(UUID(as_uuid=True), ForeignKey("livestock_animals.id"), nullable=False)
    ranch_id = Column(UUID(as_uuid=True), ForeignKey("livestock_ranches.id"), nullable=False)
    starting_price_cents = Column(Integer, nullable=False)
    current_price_cents = Column(Integer, nullable=False)
    highest_bid_user_id = Column(UUID(as_uuid=True), ForeignKey("livestock_users.id"), nullable=True)
    ends_at = Column(DateTime, nullable=False)
    status = Column(String(16), nullable=False, default="open")  # open|closed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AuctionBid(Base):
    __tablename__ = "livestock_auction_bids"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    auction_id = Column(UUID(as_uuid=True), ForeignKey("livestock_auctions.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("livestock_users.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
