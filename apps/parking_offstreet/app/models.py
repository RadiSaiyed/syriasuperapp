import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Index, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


def default_uuid():
    return uuid.uuid4()


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (Index("ix_facility_name", "name"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    operator_id = Column(UUID(as_uuid=True), nullable=True)
    name = Column(String(128), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    height_limit_m = Column(Float, nullable=True)
    opening_hours_json = Column(String(4096), nullable=True)


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (Index("ix_res_user", "user_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id"), nullable=False)
    from_ts = Column(DateTime, nullable=False)
    to_ts = Column(DateTime, nullable=False)
    price_cents = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="reserved")  # reserved|canceled|checked_in|completed
    qr_code = Column(String(64), nullable=False)  # opaque token
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Entry(Base):
    __tablename__ = "entries"
    __table_args__ = (
        Index("ix_entry_fac", "facility_id"),
        Index("ix_entry_created", "created_at"),
        UniqueConstraint("reservation_id", name="uq_entry_reservation"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id"), nullable=False)
    reservation_id = Column(UUID(as_uuid=True), ForeignKey("reservations.id"), nullable=True)
    plate = Column(String(32), nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    stopped_at = Column(DateTime, nullable=True)
    price_cents = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

