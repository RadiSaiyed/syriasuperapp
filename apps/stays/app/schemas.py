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
    is_favorite: Optional[bool] = None
    image_url: Optional[str] = None
    favorites_count: Optional[int] = None
    price_preview_total_cents: Optional[int] = None
    price_preview_nightly_cents: Optional[int] = None
    distance_km: Optional[float] = None
    badges: List[str] = []


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
    rating_histogram: dict[str, int] = {}
    similar: List["PropertyOut"] = []


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
    # Booking-like enhancements
    sort_by: Literal["price", "rating", "popularity", "distance"] = "price"
    sort_order: Literal["asc", "desc"] = "asc"
    center_lat: Optional[float] = None
    center_lon: Optional[float] = None
    min_rating: Optional[int] = Field(default=None, ge=1, le=5)
    # Popular UX filters mapped to amenities
    free_cancellation: Optional[bool] = None
    breakfast_included: Optional[bool] = None
    non_refundable: Optional[bool] = None
    pay_at_property: Optional[bool] = None
    no_prepayment: Optional[bool] = None
    # Optional map bounds (if provided, filters properties within box)
    min_lat: Optional[float] = None
    max_lat: Optional[float] = None
    min_lon: Optional[float] = None
    max_lon: Optional[float] = None
    # Optional explicit property filter
    property_ids: Optional[List[str]] = None
    # Aggregate one result per property (cheapest unit)
    group_by_property: bool = False
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
    property_image_url: Optional[str] = None
    property_rating_avg: Optional[float] = None
    property_rating_count: Optional[int] = None
    distance_km: Optional[float] = None
    badges: List[str] = []
    policy_free_cancellation: Optional[bool] = None
    policy_non_refundable: Optional[bool] = None
    policy_no_prepayment: Optional[bool] = None
    policy_pay_at_property: Optional[bool] = None


class SearchFacetsOut(BaseModel):
    amenities_counts: dict[str, int] = {}
    rating_bands: dict[str, int] = {}
    price_min_cents: Optional[int] = None
    price_max_cents: Optional[int] = None
    price_histogram: dict[str, int] = {}


class SearchAvailabilityOut(BaseModel):
    results: List[AvailableUnitOut]
    total: Optional[int] = None
    next_offset: Optional[int] = None
    facets: Optional[SearchFacetsOut] = None


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


class UnitCalendarDayOut(BaseModel):
    date: date
    available_units: int
    price_cents: int


class UnitCalendarOut(BaseModel):
    unit_id: str
    days: List[UnitCalendarDayOut]


class PropertyCalendarDayOut(BaseModel):
    date: date
    available_units_total: int
    min_price_cents: int


class PropertyCalendarOut(BaseModel):
    property_id: str
    days: List[PropertyCalendarDayOut]


class CityPopularOut(BaseModel):
    city: str
    property_count: int
    avg_rating: Optional[float] = None
    image_url: Optional[str] = None
    min_price_cents: Optional[int] = None


class SuggestItemOut(BaseModel):
    type: Literal["city", "property"]
    id: Optional[str] = None
    name: str
    city: Optional[str] = None
    rating_avg: Optional[float] = None
    image_url: Optional[str] = None


class SuggestOut(BaseModel):
    items: List[SuggestItemOut]
