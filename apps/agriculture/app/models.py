import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


def default_uuid():
    return uuid.uuid4()


class User(Base):
    __tablename__ = "agri_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    phone = Column(String(32), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=True)
    role = Column(String(24), nullable=False, default="buyer")  # buyer|farmer|worker
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    farm = relationship("Farm", back_populates="owner", uselist=False)
    applications = relationship("Application", back_populates="applicant")
    orders = relationship("Order", back_populates="buyer")


class Farm(Base):
    __tablename__ = "agri_farms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("agri_users.id"), nullable=False, unique=True)
    name = Column(String(128), nullable=False)
    location = Column(String(128), nullable=True)
    description = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="farm")
    listings = relationship("Listing", back_populates="farm")
    jobs = relationship("Job", back_populates="farm")


class Listing(Base):
    __tablename__ = "agri_listings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    farm_id = Column(UUID(as_uuid=True), ForeignKey("agri_farms.id"), nullable=False)
    produce_name = Column(String(128), nullable=False)
    category = Column(String(64), nullable=True)  # e.g., fruit, vegetable
    quantity_kg = Column(Integer, nullable=False)
    price_per_kg_cents = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="active")  # active|sold_out
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    farm = relationship("Farm", back_populates="listings")
    orders = relationship("Order", back_populates="listing")


class Order(Base):
    __tablename__ = "agri_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    buyer_user_id = Column(UUID(as_uuid=True), ForeignKey("agri_users.id"), nullable=False)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("agri_listings.id"), nullable=False)
    qty_kg = Column(Integer, nullable=False)
    total_cents = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="created")  # created|confirmed|canceled
    payment_request_id = Column(String(64), nullable=True)
    payment_transfer_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    buyer = relationship("User", back_populates="orders")
    listing = relationship("Listing", back_populates="orders")


class Job(Base):
    __tablename__ = "agri_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    farm_id = Column(UUID(as_uuid=True), ForeignKey("agri_farms.id"), nullable=False)
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(128), nullable=True)
    wage_per_day_cents = Column(Integer, nullable=True)
    start_date = Column(String(16), nullable=True)  # ISO date string for MVP
    end_date = Column(String(16), nullable=True)    # ISO date string for MVP
    status = Column(String(16), nullable=False, default="open")  # open|closed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    farm = relationship("Farm", back_populates="jobs")
    applications = relationship("Application", back_populates="job")


class Application(Base):
    __tablename__ = "agri_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    job_id = Column(UUID(as_uuid=True), ForeignKey("agri_jobs.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("agri_users.id"), nullable=False)
    message = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="applied")  # applied|reviewed|accepted|rejected|withdrawn
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    job = relationship("Job", back_populates="applications")
    applicant = relationship("User", back_populates="applications")
