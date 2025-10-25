import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, ForeignKey, Date, Index, UniqueConstraint
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

    accounts = relationship("BillerAccount", back_populates="user")
    bills = relationship("Bill", back_populates="user")
    topups = relationship("Topup", back_populates="user")


class Biller(Base):
    __tablename__ = "billers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    name = Column(String(128), nullable=False)
    category = Column(String(32), nullable=False)  # electricity, water, mobile
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    products = relationship("BillerProduct", back_populates="biller")
    accounts = relationship("BillerAccount", back_populates="biller")


class BillerProduct(Base):
    __tablename__ = "biller_products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    biller_id = Column(UUID(as_uuid=True), ForeignKey("billers.id"), nullable=False)
    name = Column(String(128), nullable=False)  # e.g., Prepaid Topup, Postpaid Bill
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    biller = relationship("Biller", back_populates="products")


class BillerAccount(Base):
    __tablename__ = "biller_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    biller_id = Column(UUID(as_uuid=True), ForeignKey("billers.id"), nullable=False)
    account_ref = Column(String(64), nullable=False)  # meter number / phone number
    alias = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="accounts")
    biller = relationship("Biller", back_populates="accounts")


class Bill(Base):
    __tablename__ = "bills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    biller_id = Column(UUID(as_uuid=True), ForeignKey("billers.id"), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("biller_accounts.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="pending")  # pending|paid|canceled
    due_date = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    payment_request_id = Column(String(64), nullable=True)

    user = relationship("User", back_populates="bills")


class Topup(Base):
    __tablename__ = "topups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    operator_biller_id = Column(UUID(as_uuid=True), ForeignKey("billers.id"), nullable=False)
    target_phone = Column(String(32), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="created")  # created|paid|failed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    payment_request_id = Column(String(64), nullable=True)

    user = relationship("User", back_populates="topups")


class PromoCode(Base):
    __tablename__ = "util_promo_codes"
    __table_args__ = (
        Index('ix_util_promo_code', 'code', unique=True),
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
    __tablename__ = "util_promo_redemptions"
    __table_args__ = (
        UniqueConstraint('topup_id', name='uq_util_promo_redemption_topup'),
        Index('ix_util_promo_redemptions_promo', 'promo_code_id'),
        Index('ix_util_promo_redemptions_user', 'user_id'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    promo_code_id = Column(UUID(as_uuid=True), ForeignKey("util_promo_codes.id"), nullable=False)
    topup_id = Column(UUID(as_uuid=True), ForeignKey("topups.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AutoPayRule(Base):
    __tablename__ = "util_autopay_rules"
    __table_args__ = (
        Index('ix_util_autopay_user', 'user_id'),
        Index('ix_util_autopay_account', 'account_id'),
        UniqueConstraint('user_id', 'account_id', name='uq_util_autopay_user_account'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("biller_accounts.id"), nullable=False)
    day_of_month = Column(Integer, nullable=True)  # 1..28 (or None for due_date based)
    max_amount_cents = Column(Integer, nullable=True)  # cap per bill
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
