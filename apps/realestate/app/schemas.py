from pydantic import BaseModel, Field
from typing import Optional, List


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


class ListingOut(BaseModel):
    id: str
    title: str
    city: str
    district: Optional[str] = None
    type: str
    property_type: str
    price_cents: int
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    size_sqm: Optional[float] = None
    images: Optional[List[str]] = None
    owner_phone: Optional[str] = None


class ListingsListOut(BaseModel):
    listings: List[ListingOut]


class InquiryCreateIn(BaseModel):
    listing_id: str
    message: Optional[str] = Field(default=None, max_length=512)


class InquiryOut(BaseModel):
    id: str
    listing_id: str
    message: Optional[str] = None


class InquiriesListOut(BaseModel):
    items: List[InquiryOut]


class ReservationOut(BaseModel):
    id: str
    listing_id: str
    payment_request_id: str | None = None
    amount_cents: int
    status: str
    owner_decision: str
    title: Optional[str] = None
    city: Optional[str] = None


class ReservationsListOut(BaseModel):
    items: List[ReservationOut]
