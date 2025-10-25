# carmarket
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


def default_uuid():
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    phone = Column(String(32), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    listings = relationship("Listing", back_populates="seller")
    offers = relationship("Offer", back_populates="buyer")


class Listing(Base):
    __tablename__ = "listings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    seller_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String(128), nullable=False)
    make = Column(String(64), nullable=True)
    model = Column(String(64), nullable=True)
    year = Column(Integer, nullable=True)
    price_cents = Column(Integer, nullable=False, default=0)
    description = Column(String(2048), nullable=True)
    mileage_km = Column(Integer, nullable=True)
    condition = Column(String(32), nullable=True)  # new|used|damaged
    city = Column(String(64), nullable=True)
    status = Column(String(16), nullable=False, default="active")  # active|sold|hidden
    views_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    seller = relationship("User", back_populates="listings")
    offers = relationship("Offer", back_populates="listing")


class ListingImage(Base):
    __tablename__ = "listing_images"
    __table_args__ = (
        Index("ix_listing_images_listing", "listing_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False)
    url = Column(String(1024), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Offer(Base):
    __tablename__ = "offers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False)
    buyer_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="pending")  # pending|accepted|rejected|canceled
    payment_request_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    listing = relationship("Listing", back_populates="offers")
    buyer = relationship("User", back_populates="offers")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_listing", "listing_id"),
        Index("ix_chat_created", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False)
    from_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    content = Column(String(2000), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class SellerReview(Base):
    __tablename__ = "seller_reviews"
    __table_args__ = (
        UniqueConstraint("offer_id", name="uq_seller_review_offer"),
        Index("ix_seller_review_seller", "seller_user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    offer_id = Column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=False)
    seller_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    buyer_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(String(1024), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
