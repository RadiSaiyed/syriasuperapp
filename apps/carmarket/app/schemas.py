# carmarket
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


class ListingCreateIn(BaseModel):
    title: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    price_cents: int
    description: Optional[str] = None
    mileage_km: Optional[int] = None
    condition: Optional[str] = None
    city: Optional[str] = None


class ListingOut(BaseModel):
    id: str
    title: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    price_cents: int
    seller_user_id: str
    mileage_km: Optional[int] = None
    condition: Optional[str] = None
    city: Optional[str] = None
    status: Optional[str] = None
    images: Optional[List[str]] = None


class ListingsListOut(BaseModel):
    listings: List[ListingOut]


class OfferCreateIn(BaseModel):
    amount_cents: int


class OfferOut(BaseModel):
    id: str
    listing_id: str
    buyer_user_id: str
    amount_cents: int
    status: str
    payment_request_id: Optional[str] = None


class OffersListOut(BaseModel):
    offers: List[OfferOut]


class FavoritesListOut(BaseModel):
    listings: List[ListingOut]


class ListingImageIn(BaseModel):
    url: str


class ChatMessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    to_user_id: Optional[str] = None


class ChatMessageOut(BaseModel):
    id: str
    listing_id: str
    from_user_id: str
    to_user_id: Optional[str]
    content: str
    created_at: datetime


class ChatMessagesListOut(BaseModel):
    messages: List[ChatMessageOut]


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None


class ReviewOut(BaseModel):
    id: str
    offer_id: str
    seller_user_id: str
    buyer_user_id: str
    rating: int
    comment: Optional[str]
    created_at: datetime
