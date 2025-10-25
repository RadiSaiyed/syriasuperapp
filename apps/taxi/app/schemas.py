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


class UserOut(BaseModel):
    id: str
    phone: str
    name: Optional[str]
    role: str


class DriverApplyIn(BaseModel):
    vehicle_make: Optional[str] = None
    vehicle_plate: Optional[str] = None


class DriverStatusIn(BaseModel):
    status: str  # offline|available|busy


class DriverLocationIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class StopIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class RideRequestIn(BaseModel):
    pickup_lat: float = Field(ge=-90, le=90)
    pickup_lon: float = Field(ge=-180, le=180)
    dropoff_lat: float = Field(ge=-90, le=90)
    dropoff_lon: float = Field(ge=-180, le=180)
    stops: Optional[List[StopIn]] = None
    promo_code: Optional[str] = None
    prepay: Optional[bool] = None
    # Ride class (category)
    ride_class: Optional[str] = Field(default=None, description="standard|comfort|yellow|vip|van|electro")
    # New: order on behalf of someone else
    for_name: Optional[str] = Field(default=None, max_length=128)
    for_phone: Optional[str] = Field(default=None, max_length=32)
    # Payment mode: 'self' (ordering rider pays, typically escrow) or 'cash' (passenger pays driver)
    pay_mode: Optional[str] = Field(default=None)


class RideOut(BaseModel):
    id: str
    status: str
    rider_user_id: str
    driver_id: Optional[str] = None
    quoted_fare_cents: int
    final_fare_cents: Optional[int] = None
    distance_km: Optional[float] = None
    payment_request_id: Optional[str] = None
    surge_multiplier: Optional[float] = None
    eta_to_pickup_minutes: Optional[int] = None
    stops: Optional[List[StopIn]] = None
    applied_promo_code: Optional[str] = None
    discount_cents: Optional[int] = None
    route_polyline: Optional[str] = None
    ride_class: Optional[str] = None
    # New: beneficiary + payer mode
    for_name: Optional[str] = None
    for_phone: Optional[str] = None
    pay_mode: Optional[str] = None
    platform_fee_cents: Optional[int] = None
    rider_reward_applied: Optional[bool] = None
    driver_reward_fee_waived: Optional[bool] = None
    pickup_lat: Optional[float] = None
    pickup_lon: Optional[float] = None
    dropoff_lat: Optional[float] = None
    dropoff_lon: Optional[float] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    my_rating: Optional[int] = None
    my_rating_comment: Optional[str] = None
    my_rating_created_at: Optional[datetime] = None


class RidesListOut(BaseModel):
    rides: List[RideOut]


class RideQuoteOut(BaseModel):
    quoted_fare_cents: int
    distance_km: float
    surge_multiplier: float
    final_quote_cents: int
    eta_to_pickup_minutes: Optional[int] = None
    applied_promo_code: Optional[str] = None
    discount_cents: Optional[int] = None
    route_polyline: Optional[str] = None
    ride_class: Optional[str] = None


class RideReceiptOut(BaseModel):
    ride_id: str
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    rider_phone: Optional[str] = None
    driver_phone: Optional[str] = None
    passenger_name: Optional[str] = None
    passenger_phone: Optional[str] = None
    pay_mode: Optional[str] = None  # self|cash
    payment_method: Optional[str] = None  # escrow|cash|unknown
    rider_reward_applied: Optional[bool] = None
    driver_reward_fee_waived: Optional[bool] = None
    payment_status: Optional[str] = None  # released|held|cash|unknown
    fare_cents: int
    platform_fee_cents: int
    driver_take_home_cents: int
    distance_km: Optional[float] = None
    escrow_amount_cents: Optional[int] = None
    escrow_released: Optional[bool] = None


class RideRatingIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None


# Partners / Third‑Party integrations
class PartnerRegisterIn(BaseModel):
    name: str
    key_id: str
    secret: str


class DispatchCreateIn(BaseModel):
    ride_id: str
    partner_key_id: str
    external_trip_id: Optional[str] = None


class DispatchOut(BaseModel):
    id: str
    ride_id: str
    partner_key_id: str
    external_trip_id: str
    status: str
    created_at: str
    updated_at: str


class RideStatusWebhookIn(BaseModel):
    external_trip_id: str
    status: str  # accepted|enroute|completed|canceled
    final_fare_cents: Optional[int] = None


class DriverLocationWebhookIn(BaseModel):
    external_driver_id: str
    lat: float
    lon: float


class DriverRatingsOut(BaseModel):
    avg_rating: Optional[float]
    ratings_count: int


class DriverProfileOut(BaseModel):
    id: str
    phone: str
    name: Optional[str]
    status: str
    vehicle_make: Optional[str]
    vehicle_plate: Optional[str]
    avg_rating: Optional[float]
    ratings_count: int


class CancelIn(BaseModel):
    reason: Optional[str] = None


class FavoriteIn(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class FavoriteOut(BaseModel):
    id: str
    label: str
    lat: float
    lon: float


class FavoriteUpdateIn(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=64)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)


class ScheduleRideIn(BaseModel):
    pickup_lat: float = Field(ge=-90, le=90)
    pickup_lon: float = Field(ge=-180, le=180)
    dropoff_lat: float = Field(ge=-90, le=90)
    dropoff_lon: float = Field(ge=-180, le=180)
    stops: Optional[List[StopIn]] = None
    promo_code: Optional[str] = None
    scheduled_for: datetime


class ScheduleRideOut(BaseModel):
    id: str
    scheduled_for: datetime
    quoted_fare_cents: int
    final_quote_cents: int
    distance_km: float
    surge_multiplier: float
    applied_promo_code: Optional[str] = None
    discount_cents: Optional[int] = None


class PromoCreateIn(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    percent_off_bps: Optional[int] = Field(default=None, ge=0, le=10000)
    amount_off_cents: Optional[int] = Field(default=None, ge=0)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    max_uses: Optional[int] = Field(default=None, ge=1)
    per_user_max_uses: Optional[int] = Field(default=None, ge=1)
    min_fare_cents: Optional[int] = Field(default=None, ge=0)
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
    min_fare_cents: Optional[int]
    active: bool


# Scheduled rides listing
class ScheduledRideItemOut(BaseModel):
    id: str
    scheduled_for: datetime
    pickup_lat: float
    pickup_lon: float
    dropoff_lat: float
    dropoff_lon: float
    applied_promo_code: Optional[str] = None
    stops: Optional[List[StopIn]] = None


class ScheduledRidesListOut(BaseModel):
    scheduled: List[ScheduledRideItemOut]
