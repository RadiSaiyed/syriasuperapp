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

    bookings = relationship("Booking", back_populates="user")


class Airline(Base):
    __tablename__ = "airlines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    name = Column(String(128), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    flights = relationship("Flight", back_populates="airline")


class Flight(Base):
    __tablename__ = "flights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    airline_id = Column(UUID(as_uuid=True), ForeignKey("airlines.id"), nullable=False)
    origin = Column(String(64), nullable=False)
    destination = Column(String(64), nullable=False)
    depart_at = Column(DateTime, nullable=False)
    arrive_at = Column(DateTime, nullable=True)
    price_cents = Column(Integer, nullable=False)
    seats_total = Column(Integer, nullable=False, default=180)
    seats_available = Column(Integer, nullable=False, default=180)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    airline = relationship("Airline", back_populates="flights")
    bookings = relationship("Booking", back_populates="flight")


class FlightSeat(Base):
    __tablename__ = "flight_seats"
    __table_args__ = (
        UniqueConstraint('flight_id', 'seat_number', name='uq_flight_seat'),
        Index('ix_flight_seats_flight', 'flight_id'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    flight_id = Column(UUID(as_uuid=True), ForeignKey("flights.id"), nullable=False)
    seat_number = Column(Integer, nullable=False)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    flight_id = Column(UUID(as_uuid=True), ForeignKey("flights.id"), nullable=False)
    status = Column(String(24), nullable=False, default="reserved")  # reserved|confirmed|canceled
    seats_count = Column(Integer, nullable=False, default=1)
    total_price_cents = Column(Integer, nullable=False)
    payment_request_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="bookings")
    flight = relationship("Flight", back_populates="bookings")


class PromoCode(Base):
    __tablename__ = "flight_promo_codes"
    __table_args__ = (
        Index('ix_flight_promo_code', 'code', unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    code = Column(String(32), nullable=False, unique=True)
    percent_off_bps = Column(Integer, nullable=True)
    amount_off_cents = Column(Integer, nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    max_uses = Column(Integer, nullable=True)
    per_user_max_uses = Column(Integer, nullable=True)
    uses_count = Column(Integer, nullable=False, default=0)
    min_total_cents = Column(Integer, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PromoRedemption(Base):
    __tablename__ = "flight_promo_redemptions"
    __table_args__ = (
        UniqueConstraint('booking_id', name='uq_flight_promo_redemption_booking'),
        Index('ix_flight_promo_redemptions_promo', 'promo_code_id'),
        Index('ix_flight_promo_redemptions_user', 'user_id'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    promo_code_id = Column(UUID(as_uuid=True), ForeignKey("flight_promo_codes.id"), nullable=False)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

