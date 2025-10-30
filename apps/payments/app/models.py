import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Index,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


def default_uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    phone = Column(String(32), nullable=False, unique=True, index=True)
    username = Column(String(64), nullable=True, unique=True, index=True)
    password_hash = Column(String(128), nullable=True)
    name = Column(String(128), nullable=True)
    is_merchant = Column(Boolean, nullable=False, default=False)
    is_agent = Column(Boolean, nullable=False, default=False)
    merchant_status = Column(String(32), nullable=False, default="none")  # none, applied, approved, rejected
    kyc_level = Column(Integer, nullable=False, default=0)  # 0=none,1=basic,2=full
    kyc_status = Column(String(32), nullable=False, default="none")  # none,pending,approved,rejected
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    wallet = relationship("Wallet", uselist=False, back_populates="user")
    merchant = relationship("Merchant", uselist=False, back_populates="user")


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    balance_cents = Column(Integer, nullable=False, default=0)
    currency_code = Column(String(8), nullable=False, default="SYP")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="wallet")
    entries = relationship("LedgerEntry", back_populates="wallet")


class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_transfers_idempotency"),
        Index("ix_transfers_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    from_wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=True)
    to_wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency_code = Column(String(8), nullable=False, default="SYP")
    status = Column(String(32), nullable=False, default="completed")
    idempotency_key = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    from_wallet = relationship("Wallet", foreign_keys=[from_wallet_id])
    to_wallet = relationship("Wallet", foreign_keys=[to_wallet_id])
    entries = relationship("LedgerEntry", back_populates="transfer")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (Index("ix_ledger_wallet_id_created", "wallet_id", "created_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    transfer_id = Column(UUID(as_uuid=True), ForeignKey("transfers.id"), nullable=False)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)
    amount_cents_signed = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    transfer = relationship("Transfer", back_populates="entries")
    wallet = relationship("Wallet", back_populates="entries")


class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_refunds_idem"),
        Index("ix_refunds_original_created", "original_transfer_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    original_transfer_id = Column(UUID(as_uuid=True), ForeignKey("transfers.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency_code = Column(String(8), nullable=False, default="SYP")
    status = Column(String(32), nullable=False, default="completed")  # completed, failed
    idempotency_key = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    original_transfer = relationship("Transfer")


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    fee_bps = Column(Integer, nullable=True)

    user = relationship("User", back_populates="merchant")
    wallet = relationship("Wallet")
    qrs = relationship("QRCode", back_populates="merchant")


class MerchantApiKey(Base):
    __tablename__ = "merchant_api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    key_id = Column(String(32), nullable=False, unique=True, index=True)
    secret = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    scope = Column(String(128), nullable=True)

    user = relationship("User")


class QRCode(Base):
    __tablename__ = "qr_codes"
    __table_args__ = (
        UniqueConstraint("code", name="uq_qr_code"),
        Index("ix_qr_expires", "expires_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False)
    code = Column(String(128), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency_code = Column(String(8), nullable=False, default="SYP")
    expires_at = Column(DateTime, nullable=False)
    status = Column(String(32), nullable=False, default="active")  # active, used, expired
    mode = Column(String(16), nullable=False, default="dynamic")  # dynamic (one-time, fixed amount) | static (reusable, variable amount)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    merchant = relationship("Merchant", back_populates="qrs")


class CashRequest(Base):
    __tablename__ = "cash_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    type = Column(String(16), nullable=False)  # cashin, cashout
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agent_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    amount_cents = Column(Integer, nullable=False)
    currency_code = Column(String(8), nullable=False, default="SYP")
    status = Column(String(32), nullable=False, default="pending")  # pending, accepted, rejected, canceled, completed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    idempotency_key = Column(String(64), nullable=True)
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_cash_requests_idem"),)

    user = relationship("User", foreign_keys=[user_id])
    agent = relationship("User", foreign_keys=[agent_user_id])


class PaymentRequest(Base):
    __tablename__ = "payment_requests"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_payment_requests_idem"),
        Index("ix_pr_target_created", "target_user_id", "created_at"),
        Index("ix_pr_requester_created", "requester_user_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    requester_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    target_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency_code = Column(String(8), nullable=False, default="SYP")
    status = Column(String(32), nullable=False, default="pending")  # pending, accepted, rejected, canceled, expired
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    idempotency_key = Column(String(64), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    requester = relationship("User", foreign_keys=[requester_user_id])
    target = relationship("User", foreign_keys=[target_user_id])


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    type = Column(String(64), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    data = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    url = Column(String(512), nullable=False)
    secret = Column(String(64), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User")


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    endpoint_id = Column(UUID(as_uuid=True), ForeignKey("webhook_endpoints.id"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(16), nullable=False, default="pending")  # pending, delivered, failed
    attempt_count = Column(Integer, nullable=False, default=0)
    last_error = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)
    last_attempt_at = Column(DateTime, nullable=True)
    next_attempt_at = Column(DateTime, nullable=True)


class PaymentLink(Base):
    __tablename__ = "payment_links"
    __table_args__ = (
        UniqueConstraint("code", name="uq_links_code"),
        Index("ix_links_user_created", "user_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    code = Column(String(128), nullable=False)
    amount_cents = Column(Integer, nullable=False, default=0)  # 0 for static (variable)
    currency_code = Column(String(8), nullable=False, default="SYP")
    mode = Column(String(16), nullable=False, default="dynamic")  # dynamic|static
    status = Column(String(32), nullable=False, default="active")  # active, used, expired, canceled
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User")


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_sub_payer_status", "payer_user_id", "status"),
        Index("ix_sub_next_charge", "next_charge_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    payer_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    merchant_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency_code = Column(String(8), nullable=False, default="SYP")
    interval_days = Column(Integer, nullable=False, default=30)
    next_charge_at = Column(DateTime, nullable=False)
    status = Column(String(32), nullable=False, default="active")  # active, canceled
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    payer = relationship("User", foreign_keys=[payer_user_id])
    merchant = relationship("User", foreign_keys=[merchant_user_id])


class TopupVoucher(Base):
    __tablename__ = "topup_vouchers"
    __table_args__ = (
        UniqueConstraint("code", name="uq_voucher_code"),
        Index("ix_voucher_status_created", "status", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    code = Column(String(64), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency_code = Column(String(8), nullable=False, default="SYP")
    status = Column(String(16), nullable=False, default="active")  # active|redeemed|revoked
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    redeemed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    redeemed_at = Column(DateTime, nullable=True)

    created_by = relationship("User", foreign_keys=[created_by_user_id])
    redeemed_by = relationship("User", foreign_keys=[redeemed_by_user_id])


class EBillMandate(Base):
    __tablename__ = "ebill_mandates"
    __table_args__ = (
        UniqueConstraint("payer_user_id", "issuer_user_id", name="uq_ebill_mandate_pair"),
        Index("ix_ebill_mandate_payer", "payer_user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    payer_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    issuer_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    autopay = Column(Boolean, nullable=False, default=False)
    max_amount_cents = Column(Integer, nullable=True)
    status = Column(String(16), nullable=False, default="active")  # active|revoked
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    payer = relationship("User", foreign_keys=[payer_user_id])
    issuer = relationship("User", foreign_keys=[issuer_user_id])


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoice_payer_status", "payer_user_id", "status"),
        Index("ix_invoice_due_at", "due_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    issuer_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    payer_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency_code = Column(String(8), nullable=False, default="SYP")
    status = Column(String(32), nullable=False, default="pending")  # pending|paid|canceled|expired
    reference = Column(String(128), nullable=True)
    description = Column(String(512), nullable=True)
    due_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    paid_transfer_id = Column(UUID(as_uuid=True), ForeignKey("transfers.id"), nullable=True)

    issuer = relationship("User", foreign_keys=[issuer_user_id])
    payer = relationship("User", foreign_keys=[payer_user_id])
    paid_transfer = relationship("Transfer", foreign_keys=[paid_transfer_id])


class PasskeyCredential(Base):
    __tablename__ = "passkey_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    credential_id = Column(String(256), nullable=False, unique=True)
    public_key = Column(String(1024), nullable=True)
    sign_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User")


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_idem_user_key"),
        Index("ix_idem_user_created", "user_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    key = Column(String(64), nullable=False)
    method = Column(String(8), nullable=False)
    path = Column(String(256), nullable=False)
    body_hash = Column(String(64), nullable=False)  # sha256 hex
    status = Column(String(16), nullable=False, default="in_progress")  # in_progress|completed
    result_ref = Column(String(64), nullable=True)  # e.g., transfer id
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User")
