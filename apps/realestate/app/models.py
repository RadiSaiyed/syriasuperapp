import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Float, Index, Text
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


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (Index("ix_listings_created", "created_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    title = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    city = Column(String(64), nullable=False)
    district = Column(String(64), nullable=True)
    type = Column(String(16), nullable=False, default="rent")  # rent|sale
    property_type = Column(String(24), nullable=False, default="apartment")  # apartment|house|land|office
    price_cents = Column(Integer, nullable=False)
    owner_phone = Column(String(32), nullable=True)
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Integer, nullable=True)
    size_sqm = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    images = relationship("ListingImage", back_populates="listing")


class ListingImage(Base):
    __tablename__ = "listing_images"
    __table_args__ = (Index("ix_listing_images_listing", "listing_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False)
    url = Column(String(256), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    listing = relationship("Listing", back_populates="images")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (Index("ix_favorites_user", "user_id"), Index("ix_favorites_listing", "listing_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Inquiry(Base):
    __tablename__ = "inquiries"
    __table_args__ = (Index("ix_inquiries_user", "user_id"), Index("ix_inquiries_listing", "listing_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False)
    message = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        Index("ix_reservations_listing", "listing_id"),
        Index("ix_reservations_owner", "owner_phone"),
        Index("ix_reservations_renter", "renter_user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False)
    renter_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    owner_phone = Column(String(32), nullable=True)
    payment_request_id = Column(String(64), nullable=True)
    amount_cents = Column(Integer, nullable=False, default=0)
    status = Column(String(16), nullable=False, default="pending")  # pending|completed|canceled
    owner_decision = Column(String(16), nullable=False, default="pending")  # pending|accepted|rejected
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
