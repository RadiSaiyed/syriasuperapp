from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime, date


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
    role: Optional[str] = Field(None, description="guest|host")


class PropertyCreateIn(BaseModel):
    name: str
    type: Literal["hotel", "apartment"] | str = Field(default="apartment")
    city: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None


class PropertyOut(BaseModel):
    id: str
    name: str
    type: str
    city: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    rating_avg: Optional[float] = None
    rating_count: Optional[int] = None


class UnitCreateIn(BaseModel):
    name: str
    capacity: int = Field(ge=1, le=12)
    total_units: int = Field(ge=1, le=100)
    price_cents_per_night: int = Field(ge=0)
    min_nights: int = Field(default=1, ge=1, le=60)
    cleaning_fee_cents: int = Field(default=0, ge=0)
    amenities: Optional[List[str]] = Field(default=None, description="List of amenity tags")


class UnitOut(BaseModel):
    id: str
    property_id: str
    name: str
    capacity: int
    total_units: int
    price_cents_per_night: int
    min_nights: int
    cleaning_fee_cents: int
    active: bool
    amenities: List[str] = []


class PropertyImageOut(BaseModel):
    id: str
    url: str
    sort_order: int


class PropertyDetailOut(PropertyOut):
    units: List[UnitOut]
    images: List[PropertyImageOut] = []


class SearchAvailabilityIn(BaseModel):
    city: Optional[str] = None
    check_in: date
    check_out: date
    guests: int = Field(ge=1, le=12)
    min_price_cents: Optional[int] = Field(default=None, ge=0)
    max_price_cents: Optional[int] = Field(default=None, ge=0)
    capacity_min: Optional[int] = Field(default=None, ge=1)
    property_type: Optional[Literal["hotel", "apartment"]] = None
    amenities: Optional[List[str]] = None
    amenities_mode: Literal["any", "all"] = "any"
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class AvailableUnitOut(BaseModel):
    property_id: str
    property_name: str
    unit_id: str
    unit_name: str
    capacity: int
    available_units: int
    nightly_price_cents: int
    total_cents: int


class SearchAvailabilityOut(BaseModel):
    results: List[AvailableUnitOut]
    total: Optional[int] = None
    next_offset: Optional[int] = None


class ReservationCreateIn(BaseModel):
    unit_id: str
    check_in: date
    check_out: date
    guests: int = Field(ge=1, le=12)


class ReservationOut(BaseModel):
    id: str
    property_id: str
    unit_id: str
    status: str
    check_in: date
    check_out: date
    guests: int
    total_cents: int
    created_at: datetime
    payment_request_id: Optional[str] = None


class ReservationsListOut(BaseModel):
    reservations: List[ReservationOut]


class PropertyUpdateIn(BaseModel):
    name: Optional[str] = None
    type: Optional[Literal["hotel", "apartment"]] = None
    city: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None


class UnitUpdateIn(BaseModel):
    name: Optional[str] = None
    capacity: Optional[int] = Field(default=None, ge=1, le=12)
    total_units: Optional[int] = Field(default=None, ge=1, le=100)
    price_cents_per_night: Optional[int] = Field(default=None, ge=0)
    min_nights: Optional[int] = Field(default=None, ge=1, le=60)
    cleaning_fee_cents: Optional[int] = Field(default=None, ge=0)
    active: Optional[bool] = None
    amenities: Optional[List[str]] = Field(default=None, description="Replace amenities with given list")


class ReviewCreateIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1024)


class ReviewOut(BaseModel):
    id: str
    property_id: str
    user_id: str
    rating: int
    comment: Optional[str] = None
    created_at: datetime


class PropertyImageCreateIn(BaseModel):
    url: str
    sort_order: int = 0


class UnitBlockCreateIn(BaseModel):
    start_date: date
    end_date: date
    blocked_units: int = Field(default=1, ge=1, le=100)
    reason: Optional[str] = Field(default=None, max_length=256)


class UnitBlockOut(BaseModel):
    id: str
    unit_id: str
    start_date: date
    end_date: date
    blocked_units: int
    reason: Optional[str] = None


class UnitPriceIn(BaseModel):
    date: date
    price_cents: int = Field(ge=0)


class UnitPriceOut(BaseModel):
    unit_id: str
    date: date
    price_cents: int


class ReviewsListOut(BaseModel):
    reviews: List[ReviewOut]
