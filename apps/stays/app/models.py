import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Date, UniqueConstraint
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
    role = Column(String(24), nullable=False, default="guest")  # guest|host
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    properties = relationship("Property", back_populates="owner")
    reservations = relationship("Reservation", back_populates="guest")


class Property(Base):
    __tablename__ = "properties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(128), nullable=False)
    type = Column(String(24), nullable=False, default="apartment")  # hotel|apartment
    city = Column(String(64), nullable=True)
    description = Column(String(512), nullable=True)
    address = Column(String(256), nullable=True)
    latitude = Column(String(32), nullable=True)
    longitude = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="properties")
    units = relationship("Unit", back_populates="property")
    reservations = relationship("Reservation", back_populates="property")


class Unit(Base):
    __tablename__ = "units"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    name = Column(String(128), nullable=False)  # e.g., Deluxe Room, 2BR Apartment
    capacity = Column(Integer, nullable=False, default=2)
    total_units = Column(Integer, nullable=False, default=1)
    price_cents_per_night = Column(Integer, nullable=False, default=0)
    min_nights = Column(Integer, nullable=False, default=1)
    cleaning_fee_cents = Column(Integer, nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    property = relationship("Property", back_populates="units")
    reservations = relationship("Reservation", back_populates="unit")


class PropertyImage(Base):
    __tablename__ = "property_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    url = Column(String(1024), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id"), nullable=False)
    check_in = Column(Date, nullable=False)
    check_out = Column(Date, nullable=False)
    guests = Column(Integer, nullable=False, default=1)
    total_cents = Column(Integer, nullable=False, default=0)
    status = Column(String(16), nullable=False, default="created")  # created|confirmed|canceled
    payment_request_id = Column(String(64), nullable=True)
    payment_transfer_id = Column(String(64), nullable=True)
    refund_status = Column(String(16), nullable=True)  # requested|completed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    guest = relationship("User", back_populates="reservations")
    property = relationship("Property", back_populates="reservations")
    unit = relationship("Unit", back_populates="reservations")


class UnitBlock(Base):
    __tablename__ = "unit_blocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    blocked_units = Column(Integer, nullable=False, default=1)
    reason = Column(String(256), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class UnitPrice(Base):
    __tablename__ = "unit_prices"
    __table_args__ = (
        UniqueConstraint("unit_id", "date", name="uq_unit_prices_unit_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id"), nullable=False)
    date = Column(Date, nullable=False)
    price_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class WebhookEndpoint(Base):
    __tablename__ = "stays_webhook_endpoints"
    __table_args__ = (
        UniqueConstraint("url", name="uq_stays_webhook_url"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    url = Column(String(512), nullable=False)
    secret = Column(String(128), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class FavoriteProperty(Base):
    __tablename__ = "favorite_properties"
    __table_args__ = (
        UniqueConstraint("user_id", "property_id", name="uq_favprop_user_property"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class UnitAmenity(Base):
    __tablename__ = "unit_amenities"
    __table_args__ = (
        UniqueConstraint("unit_id", "tag", name="uq_unit_amenities_unit_tag"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id"), nullable=False)
    tag = Column(String(32), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Review(Base):
    __tablename__ = "reviews"
    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False, default=5)
    comment = Column(String(1024), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
