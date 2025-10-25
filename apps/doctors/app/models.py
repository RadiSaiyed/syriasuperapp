import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, DateTime as SaDateTime, UniqueConstraint
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
    role = Column(String(24), nullable=False, default="patient")  # patient|doctor
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    doctor_profile = relationship("DoctorProfile", back_populates="user", uselist=False)
    appointments = relationship("Appointment", back_populates="patient")


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    specialty = Column(String(64), nullable=False, index=True)
    city = Column(String(64), nullable=True, index=True)
    clinic_name = Column(String(128), nullable=True)
    address = Column(String(256), nullable=True)
    latitude = Column(String(32), nullable=True)
    longitude = Column(String(32), nullable=True)
    bio = Column(String(1024), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="doctor_profile")
    slots = relationship("AvailabilitySlot", back_populates="doctor")
    appointments = relationship("Appointment", back_populates="doctor")


class DoctorImage(Base):
    __tablename__ = "doctor_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctor_profiles.id"), nullable=False)
    url = Column(String(1024), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctor_profiles.id"), nullable=False)
    start_time = Column(SaDateTime, nullable=False)
    end_time = Column(SaDateTime, nullable=False)
    is_booked = Column(Boolean, nullable=False, default=False)
    price_cents = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    doctor = relationship("DoctorProfile", back_populates="slots")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    patient_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctor_profiles.id"), nullable=False)
    slot_id = Column(UUID(as_uuid=True), ForeignKey("availability_slots.id"), nullable=False)
    status = Column(String(16), nullable=False, default="created")  # created|confirmed|canceled|completed
    price_cents = Column(Integer, nullable=False, default=0)
    payment_request_id = Column(String(64), nullable=True)
    payment_transfer_id = Column(String(64), nullable=True)
    refund_status = Column(String(16), nullable=True)  # requested|completed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    patient = relationship("User", back_populates="appointments")
    doctor = relationship("DoctorProfile", back_populates="appointments")


class DoctorReview(Base):
    __tablename__ = "doctor_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctor_profiles.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False, default=5)
    comment = Column(String(1024), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class FavoriteDoctor(Base):
    __tablename__ = "favorite_doctors"
    __table_args__ = (
        UniqueConstraint("user_id", "doctor_id", name="uq_fav_doctor_user_doctor"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctor_profiles.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class WebhookEndpoint(Base):
    __tablename__ = "doctors_webhook_endpoints"
    __table_args__ = (
        UniqueConstraint("url", name="uq_doctors_webhook_url"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    url = Column(String(512), nullable=False)
    secret = Column(String(128), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
