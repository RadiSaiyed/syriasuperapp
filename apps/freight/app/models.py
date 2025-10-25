import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, ForeignKey, Index, UniqueConstraint, Float
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
    role = Column(String(16), nullable=False, default="shipper")  # shipper|carrier
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    carrier = relationship("CarrierProfile", uselist=False, back_populates="user")


class CarrierProfile(Base):
    __tablename__ = "carrier_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    company_name = Column(String(128), nullable=True)
    status = Column(String(16), nullable=False, default="approved")  # approved in dev
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="carrier")
    loads = relationship("Load", back_populates="carrier")


class CarrierLocation(Base):
    __tablename__ = "carrier_locations"
    __table_args__ = (
        UniqueConstraint("carrier_id", name="uq_carrier_location"),
        Index("ix_carrier_loc_updated", "updated_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    carrier_id = Column(UUID(as_uuid=True), ForeignKey("carrier_profiles.id"), nullable=False, unique=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Load(Base):
    __tablename__ = "loads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    shipper_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    carrier_id = Column(UUID(as_uuid=True), ForeignKey("carrier_profiles.id"), nullable=True)
    status = Column(String(24), nullable=False, default="posted")  # posted|assigned|picked_up|in_transit|delivered|canceled
    origin = Column(String(128), nullable=False)
    destination = Column(String(128), nullable=False)
    weight_kg = Column(Integer, nullable=False, default=0)
    price_cents = Column(Integer, nullable=False, default=0)
    payment_request_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    pickup_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    pod_url = Column(String(512), nullable=True)

    carrier = relationship("CarrierProfile", back_populates="loads")


class LoadChatMessage(Base):
    __tablename__ = "load_chat_messages"
    __table_args__ = (
        Index("ix_load_chat_load", "load_id"),
        Index("ix_load_chat_created", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    load_id = Column(UUID(as_uuid=True), ForeignKey("loads.id"), nullable=False)
    from_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content = Column(String(2000), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Bid(Base):
    __tablename__ = "bids"
    __table_args__ = (
        Index("ix_bid_load", "load_id"),
        Index("ix_bid_created", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    load_id = Column(UUID(as_uuid=True), ForeignKey("loads.id"), nullable=False)
    carrier_id = Column(UUID(as_uuid=True), ForeignKey("carrier_profiles.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="pending")  # pending|accepted|rejected|canceled
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
