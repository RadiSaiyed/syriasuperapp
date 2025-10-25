from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RequestOtpIn(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v: str) -> str:
        if not v or not v.startswith("+"):
            raise ValueError("phone must start with + and country code")
        digits = v[1:]
        if not digits.isdigit() or len(digits) < 7:
            raise ValueError("invalid phone format")
        return v


class VerifyOtpIn(BaseModel):
    phone: str
    otp: str
    session_id: str | None = None
    name: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v: str) -> str:
        if not v or not v.startswith("+"):
            raise ValueError("phone must start with + and country code")
        digits = v[1:]
        if not digits.isdigit() or len(digits) < 7:
            raise ValueError("invalid phone format")
        return v


class UserOut(BaseModel):
    id: str
    phone: str
    name: Optional[str]
    is_merchant: bool


class WalletOut(BaseModel):
    id: str
    balance_cents: int
    currency_code: str


class WalletResponse(BaseModel):
    user: UserOut
    wallet: WalletOut


class TopupIn(BaseModel):
    amount_cents: int = Field(gt=0)
    idempotency_key: str


class TransferIn(BaseModel):
    to_phone: str
    amount_cents: int = Field(gt=0)
    idempotency_key: str

    @field_validator("to_phone")
    @classmethod
    def valid_phone(cls, v: str) -> str:
        if not v or not v.startswith("+"):
            raise ValueError("to_phone must start with + and country code")
        digits = v[1:]
        if not digits.isdigit() or len(digits) < 7:
            raise ValueError("invalid phone format")
        return v


class TransferOut(BaseModel):
    transfer_id: str
    from_wallet_id: Optional[str]
    to_wallet_id: str
    amount_cents: int
    currency_code: str
    status: str


class QRCreateIn(BaseModel):
    amount_cents: int = Field(gt=0)
    currency_code: str = "SYP"
    mode: str = "dynamic"  # dynamic|static (static ignores amount here; amount provided at pay)


class QROut(BaseModel):
    code: str
    expires_at: str


class QRPayIn(BaseModel):
    code: str
    idempotency_key: str
    amount_cents: int | None = Field(default=None, gt=0)


class LedgerEntryOut(BaseModel):
    transfer_id: str
    wallet_id: str
    amount_cents_signed: int
    created_at: str


class TransactionsOut(BaseModel):
    entries: List[LedgerEntryOut]


class CreateRequestIn(BaseModel):
    to_phone: str
    amount_cents: int = Field(gt=0)
    # Optional expiry in minutes (overrides default), max 7 days
    expires_in_minutes: Optional[int] = Field(default=None, ge=1, le=7*24*60)
    metadata: Optional[dict] = None

    @field_validator("to_phone")
    @classmethod
    def valid_phone(cls, v: str) -> str:
        if not v or not v.startswith("+"):
            raise ValueError("to_phone must start with + and country code")
        digits = v[1:]
        if not digits.isdigit() or len(digits) < 7:
            raise ValueError("invalid phone format")
        return v


class RequestOut(BaseModel):
    id: str
    requester_phone: str
    target_phone: str
    amount_cents: int
    currency_code: str
    status: str
    created_at: str
    expires_at: Optional[str] = None
    metadata: Optional[dict] = None


class RequestsListOut(BaseModel):
    incoming: List[RequestOut]
    outgoing: List[RequestOut]


class CashRequestCreateIn(BaseModel):
    amount_cents: int = Field(gt=0)


class CashRequestOut(BaseModel):
    id: str
    type: str
    user_phone: str
    agent_phone: Optional[str] = None
    amount_cents: int
    currency_code: str
    status: str
    created_at: str


class CashRequestsListOut(BaseModel):
    my: List[CashRequestOut]
    incoming: List[CashRequestOut]


class RefundOut(BaseModel):
    id: str
    original_transfer_id: str
    amount_cents: int
    currency_code: str
    status: str
    created_at: str


class VoucherCreateIn(BaseModel):
    # Amount in SYP (not cents)
    amount_syp: int = Field(gt=0)
    currency_code: str = "SYP"


class VoucherOut(BaseModel):
    id: str
    code: str
    amount_cents: int
    amount_syp: int
    currency_code: str
    status: str
    qr_text: str
    created_at: str
    redeemed_at: Optional[str] = None


class VouchersListOut(BaseModel):
    items: List[VoucherOut]


class VouchersBulkCreateIn(BaseModel):
    # Amount in SYP (not cents)
    amount_syp: int = Field(gt=0)
    count: int = Field(ge=1, le=1000)
    currency_code: str = "SYP"
    prefix: Optional[str] = Field(default=None, max_length=10)


class VouchersAdminSummaryOut(BaseModel):
    total_count: int
    active_count: int
    redeemed_count: int
    revoked_count: int
    total_syp: int
    redeemed_total_syp: int
    fees_syp: int
    net_syp: int


class VoucherAdminItem(BaseModel):
    id: str
    code: str
    amount_syp: int
    status: str
    created_at: str
    redeemed_at: Optional[str] = None
    created_by_phone: Optional[str] = None
    redeemed_by_phone: Optional[str] = None


class VouchersAdminListOut(BaseModel):
    items: List[VoucherAdminItem]


# Invoices (eBill-like)
class InvoiceCreateIn(BaseModel):
    payer_phone: str
    amount_cents: int = Field(gt=0)
    due_in_days: int = Field(default=10, ge=0, le=365)
    reference: Optional[str] = Field(default=None, max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)

    @field_validator("payer_phone")
    @classmethod
    def valid_phone(cls, v: str) -> str:
        if not v or not v.startswith("+"):
            raise ValueError("payer_phone must start with + and country code")
        digits = v[1:]
        if not digits.isdigit() or len(digits) < 7:
            raise ValueError("invalid phone format")
        return v


class InvoiceOut(BaseModel):
    id: str
    issuer_phone: str
    payer_phone: str
    amount_cents: int
    currency_code: str
    status: str
    reference: Optional[str] = None
    description: Optional[str] = None
    due_at: str
    created_at: str
    paid_transfer_id: Optional[str] = None


class InvoicesListOut(BaseModel):
    incoming: List[InvoiceOut]
    outgoing: List[InvoiceOut]


class MandateUpsertIn(BaseModel):
    issuer_phone: str
    autopay: bool = False
    max_amount_cents: Optional[int] = Field(default=None, ge=1)

    @field_validator("issuer_phone")
    @classmethod
    def valid_phone(cls, v: str) -> str:
        if not v or not v.startswith("+"):
            raise ValueError("issuer_phone must start with + and country code")
        digits = v[1:]
        if not digits.isdigit() or len(digits) < 7:
            raise ValueError("invalid phone format")
        return v


class MandateOut(BaseModel):
    id: str
    issuer_phone: str
    autopay: bool
    max_amount_cents: Optional[int] = None
    status: str
    created_at: str
    updated_at: str


class MandatesListOut(BaseModel):
    items: List[MandateOut]
