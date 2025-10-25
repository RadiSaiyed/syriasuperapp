import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


def default_uuid():
    return uuid.uuid4()


class User(Base):
    __tablename__ = "carrental_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    phone = Column(String(32), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=True)
    role = Column(String(24), nullable=False, default="renter")  # renter|seller
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    company = relationship("Company", back_populates="owner", uselist=False)
    bookings = relationship("Booking", back_populates="user")


class Company(Base):
    __tablename__ = "carrental_companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("carrental_users.id"), nullable=False, unique=True)
    name = Column(String(128), nullable=False)
    location = Column(String(128), nullable=True)
    description = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="company")
    vehicles = relationship("Vehicle", back_populates="company")


class Vehicle(Base):
    __tablename__ = "carrental_vehicles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("carrental_companies.id"), nullable=False)
    make = Column(String(64), nullable=False)
    model = Column(String(64), nullable=False)
    year = Column(Integer, nullable=True)
    transmission = Column(String(16), nullable=True)  # auto|manual
    seats = Column(Integer, nullable=True)
    location = Column(String(128), nullable=True)
    price_per_day_cents = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="available")  # available|unavailable
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    company = relationship("Company", back_populates="vehicles")
    bookings = relationship("Booking", back_populates="vehicle")


class VehicleImage(Base):
    __tablename__ = "carrental_vehicle_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("carrental_vehicles.id"), nullable=False)
    url = Column(String(512), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Booking(Base):
    __tablename__ = "carrental_bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("carrental_users.id"), nullable=False)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("carrental_vehicles.id"), nullable=False)
    start_date = Column(String(16), nullable=False)  # ISO date
    end_date = Column(String(16), nullable=False)
    days = Column(Integer, nullable=False)
    total_cents = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="requested")  # requested|confirmed|canceled
    payment_request_id = Column(String(64), nullable=True)
    payment_transfer_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="bookings")
    vehicle = relationship("Vehicle", back_populates="bookings")


class FavoriteVehicle(Base):
    __tablename__ = "carrental_fav_vehicles"
    __table_args__ = (
        UniqueConstraint("user_id", "vehicle_id", name="uq_carrental_fav_user_vehicle"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("carrental_users.id"), nullable=False)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("carrental_vehicles.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
