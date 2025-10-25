from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


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


class CarrierApplyIn(BaseModel):
    company_name: Optional[str] = None


class CarrierLocationIn(BaseModel):
    lat: float
    lon: float


class LoadCreateIn(BaseModel):
    origin: str
    destination: str
    weight_kg: int = Field(ge=0)
    price_cents: int = Field(ge=0)


class LoadOut(BaseModel):
    id: str
    status: str
    shipper_user_id: str
    carrier_id: Optional[str] = None
    origin: str
    destination: str
    weight_kg: int
    price_cents: int
    payment_request_id: Optional[str] = None
    pod_url: Optional[str] = None


class LoadsListOut(BaseModel):
    loads: List[LoadOut]


class BidCreateIn(BaseModel):
    amount_cents: int = Field(ge=0)


class BidOut(BaseModel):
    id: str
    load_id: str
    carrier_id: str
    amount_cents: int
    status: str
    created_at: datetime


class BidsListOut(BaseModel):
    bids: List[BidOut]


class ChatIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class ChatMessageOut(BaseModel):
    id: str
    load_id: str
    from_user_id: str
    content: str
    created_at: datetime


class ChatListOut(BaseModel):
    messages: List[ChatMessageOut]
