import uuid
from datetime import datetime, timedelta
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
    memberships = relationship("OperatorMember", back_populates="user")


class Operator(Base):
    __tablename__ = "operators"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    name = Column(String(128), nullable=False, unique=True)
    # Optional merchant wallet phone that receives booking payments
    merchant_phone = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    trips = relationship("Trip", back_populates="operator")
    members = relationship("OperatorMember", back_populates="operator")


class OperatorMember(Base):
    __tablename__ = "operator_members"
    __table_args__ = (
        UniqueConstraint('operator_id', 'user_id', name='uq_operator_member'),
        Index('ix_operator_members_operator', 'operator_id'),
        Index('ix_operator_members_user', 'user_id'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    operator_id = Column(UUID(as_uuid=True), ForeignKey("operators.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(String(32), nullable=False, default="admin")  # admin|agent|cashier|checker
    branch_id = Column(UUID(as_uuid=True), ForeignKey("bus_operator_branches.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    operator = relationship("Operator", back_populates="members")
    user = relationship("User", back_populates="memberships")
    branch = relationship("OperatorBranch", back_populates="members")


class Trip(Base):
    __tablename__ = "trips"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    operator_id = Column(UUID(as_uuid=True), ForeignKey("operators.id"), nullable=False)
    origin = Column(String(64), nullable=False)
    destination = Column(String(64), nullable=False)
    depart_at = Column(DateTime, nullable=False)
    arrive_at = Column(DateTime, nullable=True)
    price_cents = Column(Integer, nullable=False)
    seats_total = Column(Integer, nullable=False, default=40)
    seats_available = Column(Integer, nullable=False, default=40)
    # Bus details (optional)
    bus_model = Column(String(64), nullable=True)
    bus_year = Column(Integer, nullable=True)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("bus_vehicles.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    operator = relationship("Operator", back_populates="trips")
    bookings = relationship("Booking", back_populates="trip")
    ratings = relationship("TripRating", back_populates="trip")


class TripSeat(Base):
    __tablename__ = "trip_seats"
    __table_args__ = (
        UniqueConstraint('trip_id', 'seat_number', name='uq_trip_seat'),
        Index('ix_trip_seats_trip', 'trip_id'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.id"), nullable=False)
    seat_number = Column(Integer, nullable=False)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.id"), nullable=False)
    status = Column(String(24), nullable=False, default="reserved")  # reserved|confirmed|canceled
    seats_count = Column(Integer, nullable=False, default=1)
    total_price_cents = Column(Integer, nullable=False)
    payment_request_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    # Optional: mark when ticket was validated/scanned at boarding
    boarded_at = Column(DateTime, nullable=True)
    # Optional: branch attribution for operator (for settlement/commission)
    operator_branch_id = Column(UUID(as_uuid=True), ForeignKey("bus_operator_branches.id"), nullable=True)

    user = relationship("User", back_populates="bookings")
    trip = relationship("Trip", back_populates="bookings")
    rating = relationship("TripRating", back_populates="booking", uselist=False)


class PromoCode(Base):
    __tablename__ = "bus_promo_codes"
    __table_args__ = (
        Index('ix_bus_promo_code', 'code', unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    operator_id = Column(UUID(as_uuid=True), ForeignKey("operators.id"), nullable=True)
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
    __tablename__ = "bus_promo_redemptions"
    __table_args__ = (
        UniqueConstraint('booking_id', name='uq_bus_promo_redemption_booking'),
        Index('ix_bus_promo_redemptions_promo', 'promo_code_id'),
        Index('ix_bus_promo_redemptions_user', 'user_id'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    promo_code_id = Column(UUID(as_uuid=True), ForeignKey("bus_promo_codes.id"), nullable=False)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class OperatorBranch(Base):
    __tablename__ = "bus_operator_branches"
    __table_args__ = (
        Index('ix_bus_operator_branches_operator', 'operator_id'),
        UniqueConstraint('operator_id', 'name', name='uq_operator_branch_name'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    operator_id = Column(UUID(as_uuid=True), ForeignKey("operators.id"), nullable=False)
    name = Column(String(64), nullable=False)
    commission_bps = Column(Integer, nullable=True)  # basis points (e.g., 250 = 2.5%)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    operator = relationship("Operator")
    members = relationship("OperatorMember", back_populates="branch")


class Vehicle(Base):
    __tablename__ = "bus_vehicles"
    __table_args__ = (
        Index('ix_bus_vehicles_operator', 'operator_id'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    operator_id = Column(UUID(as_uuid=True), ForeignKey("operators.id"), nullable=False)
    name = Column(String(64), nullable=False)
    seats_total = Column(Integer, nullable=False, default=40)
    seat_columns = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    operator = relationship("Operator")


class OperatorWebhook(Base):
    __tablename__ = "bus_operator_webhooks"
    __table_args__ = (
        Index('ix_bus_operator_webhooks_operator', 'operator_id'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    operator_id = Column(UUID(as_uuid=True), ForeignKey("operators.id"), nullable=False)
    url = Column(String(512), nullable=False)
    secret = Column(String(256), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    operator = relationship("Operator")


class TripRating(Base):
    __tablename__ = "trip_ratings"
    __table_args__ = (
        UniqueConstraint('booking_id', name='uq_trip_ratings_booking'),
        Index('ix_trip_ratings_trip', 'trip_id'),
        Index('ix_trip_ratings_user', 'user_id'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    booking = relationship("Booking", back_populates="rating")
    trip = relationship("Trip", back_populates="ratings")
