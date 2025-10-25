import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
    ForeignKey,
    Index,
    Float,
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


class Zone(Base):
    __tablename__ = "zones"
    __table_args__ = (Index("ix_zones_name", "name"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    name = Column(String(128), nullable=False)
    operator_id = Column(UUID(as_uuid=True), nullable=True)
    tz_code = Column(String(64), nullable=False, default="Asia/Damascus")
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)
    radius_m = Column(Integer, nullable=False, default=500)


class Tariff(Base):
    __tablename__ = "tariffs"
    __table_args__ = (Index("ix_tariff_zone", "zone_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    zone_id = Column(UUID(as_uuid=True), ForeignKey("zones.id"), nullable=False)
    currency = Column(String(8), default="SYP")
    per_minute_cents = Column(Integer, nullable=False)
    min_minutes = Column(Integer, default=10)
    free_minutes = Column(Integer, default=0)
    max_daily_cents = Column(Integer, nullable=True)
    service_fee_bps = Column(Integer, default=200)

    zone = relationship("Zone")


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        Index("ix_vehicle_user", "user_id"),
        Index("ix_vehicle_plate", "plate"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    plate = Column(String(32), nullable=False)
    country = Column(String(4), default="SY")
    default = Column(Boolean, default=True)


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_status", "user_id", "status"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    zone_id = Column(UUID(as_uuid=True), ForeignKey("zones.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    stopped_at = Column(DateTime, nullable=True)
    minutes_billed = Column(Integer, nullable=True)
    gross_cents = Column(Integer, nullable=True)
    fee_cents = Column(Integer, nullable=True)
    net_cents = Column(Integer, nullable=True)
    status = Column(String(16), default="running")  # running|stopped|settled
    escrow_transfer_id = Column(String(64), nullable=True)
    receipt_id = Column(String(64), nullable=True)
    auto_stopped_reason = Column(String(32), nullable=True)
    assumed_end_at = Column(DateTime, nullable=True)
    prepaid_minutes = Column(Integer, nullable=True)


class Receipt(Base):
    __tablename__ = "receipts"
    __table_args__ = (Index("ix_receipts_session", "session_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False, unique=True)
    minutes = Column(Integer, nullable=False)
    gross_cents = Column(Integer, nullable=False)
    fee_cents = Column(Integer, nullable=False)
    net_cents = Column(Integer, nullable=False)
    currency = Column(String(8), nullable=False, default="SYP")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (Index("ix_reminders_session", "session_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    at = Column(DateTime, nullable=False)
    type = Column(String(24), nullable=False, default="expiry")  # expiry|leave_zone
    minutes_before = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
