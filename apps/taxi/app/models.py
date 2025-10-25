import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, ForeignKey, Float, Index, UniqueConstraint, JSON
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
    role = Column(String(16), nullable=False, default="rider")  # rider|driver
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    rider_loyalty_count = Column(Integer, nullable=False, default=0)
    driver_loyalty_count = Column(Integer, nullable=False, default=0)

    driver = relationship("Driver", uselist=False, back_populates="user")


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    status = Column(String(16), nullable=False, default="offline")  # offline|available|busy
    vehicle_make = Column(String(64), nullable=True)
    vehicle_plate = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    # Optional driver class/category (standard|comfort|yellow|vip|van|electro)
    ride_class = Column(String(16), nullable=True)

    user = relationship("User", back_populates="driver")
    location = relationship("DriverLocation", uselist=False, back_populates="driver")
    rides = relationship("Ride", back_populates="driver")


class DriverLocation(Base):
    __tablename__ = "driver_locations"
    __table_args__ = (Index("ix_driver_loc_updated", "updated_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"), nullable=False, unique=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    driver = relationship("Driver", back_populates="location")


class Ride(Base):
    __tablename__ = "rides"
    __table_args__ = (Index("ix_rides_created", "created_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    rider_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"), nullable=True)
    status = Column(String(24), nullable=False, default="requested")  # requested|assigned|accepted|enroute|completed
    pickup_lat = Column(Float, nullable=False)
    pickup_lon = Column(Float, nullable=False)
    dropoff_lat = Column(Float, nullable=False)
    dropoff_lon = Column(Float, nullable=False)
    quoted_fare_cents = Column(Integer, nullable=False, default=0)
    final_fare_cents = Column(Integer, nullable=True)
    escrow_amount_cents = Column(Integer, nullable=True)
    escrow_released = Column(Boolean, nullable=False, default=False)
    # New: ride ordered for someone else
    passenger_name = Column(String(128), nullable=True)
    passenger_phone = Column(String(32), nullable=True)
    payer_mode = Column(String(16), nullable=True)  # self|cash
    ride_class = Column(String(16), nullable=True)
    distance_km = Column(Float, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    rider_reward_applied = Column(Boolean, nullable=False, default=False)
    driver_reward_fee_waived = Column(Boolean, nullable=False, default=False)

    driver = relationship("Driver", back_populates="rides")
    rating = relationship("RideRating", back_populates="ride", uselist=False)


class RideRating(Base):
    __tablename__ = "ride_ratings"
    __table_args__ = (
        Index("ix_ride_ratings_driver", "driver_id"),
        Index("ix_ride_ratings_created", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    ride_id = Column(UUID(as_uuid=True), ForeignKey("rides.id"), nullable=False, unique=True)
    rider_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1..5
    comment = Column(String(1024), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ride = relationship("Ride", back_populates="rating")


class RideStop(Base):
    __tablename__ = "ride_stops"
    __table_args__ = (
        Index("ix_ride_stops_ride", "ride_id"),
        Index("ix_ride_stops_seq", "seq"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    ride_id = Column(UUID(as_uuid=True), ForeignKey("rides.id"), nullable=False)
    seq = Column(Integer, nullable=False)  # 0..N-1
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class FavoritePlace(Base):
    __tablename__ = "favorite_places"
    __table_args__ = (
        Index("ix_fav_user", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    label = Column(String(64), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PromoCode(Base):
    __tablename__ = "promo_codes"
    __table_args__ = (
        Index("ix_promo_code", "code", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    code = Column(String(32), nullable=False, unique=True)
    percent_off_bps = Column(Integer, nullable=True)  # basis points 0..10000
    amount_off_cents = Column(Integer, nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    max_uses = Column(Integer, nullable=True)
    per_user_max_uses = Column(Integer, nullable=True)
    uses_count = Column(Integer, nullable=False, default=0)
    min_fare_cents = Column(Integer, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PromoRedemption(Base):
    __tablename__ = "promo_redemptions"
    __table_args__ = (
        UniqueConstraint("ride_id", name="uq_promo_redemption_ride"),
        Index("ix_promo_redemptions_promo", "promo_code_id"),
        Index("ix_promo_redemptions_rider", "rider_user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    promo_code_id = Column(UUID(as_uuid=True), ForeignKey("promo_codes.id"), nullable=False)
    ride_id = Column(UUID(as_uuid=True), ForeignKey("rides.id"), nullable=False)
    rider_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ScheduledRide(Base):
    __tablename__ = "scheduled_rides"
    __table_args__ = (
        Index("ix_sched_rides_when", "scheduled_for"),
        Index("ix_sched_rides_user", "rider_user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    rider_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    pickup_lat = Column(Float, nullable=False)
    pickup_lon = Column(Float, nullable=False)
    dropoff_lat = Column(Float, nullable=False)
    dropoff_lon = Column(Float, nullable=False)
    scheduled_for = Column(DateTime, nullable=False)
    promo_code = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ScheduledRideStop(Base):
    __tablename__ = "scheduled_ride_stops"
    __table_args__ = (
        Index("ix_sched_ride_stops_sched", "scheduled_ride_id"),
        Index("ix_sched_ride_stops_seq", "seq"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    scheduled_ride_id = Column(UUID(as_uuid=True), ForeignKey("scheduled_rides.id"), nullable=False)
    seq = Column(Integer, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Partner(Base):
    __tablename__ = "partners"
    __table_args__ = (
        Index("ix_partner_key", "key_id", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    name = Column(String(64), nullable=False)
    key_id = Column(String(32), nullable=False, unique=True)
    secret = Column(String(64), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PartnerDispatch(Base):
    __tablename__ = "partner_dispatches"
    __table_args__ = (
        Index("ix_pd_ride", "ride_id"),
        Index("ix_pd_partner_ext", "partner_id", "external_trip_id", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    ride_id = Column(UUID(as_uuid=True), ForeignKey("rides.id"), nullable=False)
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.id"), nullable=False)
    external_trip_id = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, default="sent")  # sent|accepted|enroute|completed|canceled|failed
    last_error = Column(String(256), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TaxiWallet(Base):
    __tablename__ = "taxi_wallets"
    __table_args__ = (
        Index("ix_taxi_wallet_driver", "driver_id", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"), nullable=False, unique=True)
    balance_cents = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    driver = relationship("Driver")


class TaxiWalletEntry(Base):
    __tablename__ = "taxi_wallet_entries"
    __table_args__ = (
        Index("ix_taxi_entry_wallet_created", "wallet_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("taxi_wallets.id"), nullable=False)
    type = Column(String(16), nullable=False)  # topup|withdraw|fee
    amount_cents_signed = Column(Integer, nullable=False)
    ride_id = Column(UUID(as_uuid=True), ForeignKey("rides.id"), nullable=True)
    original_fare_cents = Column(Integer, nullable=True)
    fee_cents = Column(Integer, nullable=True)
    driver_take_home_cents = Column(Integer, nullable=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    wallet = relationship("TaxiWallet")


class PartnerDriverMap(Base):
    __tablename__ = "partner_driver_map"
    __table_args__ = (
        Index("ix_pdm_partner_ext", "partner_id", "external_driver_id", unique=True),
        Index("ix_pdm_driver", "driver_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.id"), nullable=False)
    external_driver_id = Column(String(64), nullable=False)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class FraudEvent(Base):
    __tablename__ = "fraud_events"
    __table_args__ = (
        Index("ix_fraud_created", "created_at"),
        Index("ix_fraud_user", "user_id"),
        Index("ix_fraud_driver", "driver_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"), nullable=True)
    type = Column(String(64), nullable=False)
    data = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Suspension(Base):
    __tablename__ = "suspensions"
    __table_args__ = (
        Index("ix_susp_user", "user_id"),
        Index("ix_susp_driver", "driver_id"),
        Index("ix_susp_active_until", "active", "until"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"), nullable=True)
    reason = Column(String(256), nullable=True)
    until = Column(DateTime, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class DeviceToken(Base):
    __tablename__ = "device_tokens"
    __table_args__ = (
        Index("ix_dev_token_user", "user_id"),
        Index("ix_dev_token_token", "token", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    platform = Column(String(16), nullable=False)  # android|ios|web
    token = Column(String(256), nullable=False, unique=True)
    app_mode = Column(String(16), nullable=True)  # rider|driver
    enabled = Column(Boolean, nullable=False, default=True)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
