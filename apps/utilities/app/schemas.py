from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RequestOtpIn(BaseModel):
    phone: str


class VerifyOtpIn(BaseModel):
    phone: str
    otp: str
    session_id: Optional[str] = None
    name: Optional[str] = None


class BillerOut(BaseModel):
    id: str
    name: str
    category: str


class LinkAccountIn(BaseModel):
    biller_id: str
    account_ref: str
    alias: Optional[str] = None


class AccountOut(BaseModel):
    id: str
    biller_id: str
    account_ref: str
    alias: Optional[str] = None


class BillOut(BaseModel):
    id: str
    biller_id: str
    account_id: str
    amount_cents: int
    status: str
    due_date: Optional[date] = None
    payment_request_id: Optional[str] = None


class BillsListOut(BaseModel):
    bills: List[BillOut]


class TopupIn(BaseModel):
    operator_biller_id: str
    target_phone: str
    amount_cents: int = Field(ge=100, le=500000)
    promo_code: Optional[str] = None


class TopupOut(BaseModel):
    id: str
    operator_biller_id: str
    target_phone: str
    amount_cents: int
    status: str
    payment_request_id: Optional[str] = None
    applied_promo_code: Optional[str] = None
    discount_cents: Optional[int] = None
    final_amount_cents: Optional[int] = None


class TopupsListOut(BaseModel):
    topups: List[TopupOut]


class PromoCreateIn(BaseModel):
    code: str
    percent_off_bps: Optional[int] = Field(default=None, ge=0, le=10000)
    amount_off_cents: Optional[int] = Field(default=None, ge=0)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    max_uses: Optional[int] = Field(default=None, ge=1)
    per_user_max_uses: Optional[int] = Field(default=None, ge=1)
    min_total_cents: Optional[int] = Field(default=None, ge=0)
    active: bool = True


class PromoOut(BaseModel):
    id: str
    code: str
    percent_off_bps: Optional[int]
    amount_off_cents: Optional[int]
    valid_from: Optional[datetime]
    valid_until: Optional[datetime]
    max_uses: Optional[int]
    per_user_max_uses: Optional[int]
    uses_count: int
    min_total_cents: Optional[int]
    active: bool
