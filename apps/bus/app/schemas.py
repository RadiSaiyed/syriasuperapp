from pydantic import BaseModel, Field
from typing import Optional, List
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


class UserOut(BaseModel):
    id: str
    phone: str
    name: Optional[str]


class TripOut(BaseModel):
    id: str
    operator_name: str
    origin: str
    destination: str
    depart_at: datetime
    arrive_at: Optional[datetime] = None
    price_cents: int
    seats_available: int
    bus_model: Optional[str] = None
    bus_year: Optional[int] = None


class SearchTripsIn(BaseModel):
    origin: str
    destination: str
    date: date


class SearchTripsOut(BaseModel):
    trips: List[TripOut]


class CreateBookingIn(BaseModel):
    trip_id: str
    seats_count: int = Field(ge=1, le=6)
    seat_numbers: Optional[List[int]] = None
    promo_code: Optional[str] = None


class BookingOut(BaseModel):
    id: str
    status: str
    trip_id: str
    operator_name: str
    origin: str
    destination: str
    depart_at: datetime
    seats_count: int
    total_price_cents: int
    payment_request_id: Optional[str] = None
    seat_numbers: Optional[List[int]] = None
    merchant_phone: Optional[str] = None
    user_phone: Optional[str] = None  # included for operator views
    boarded_at: Optional[datetime] = None
    my_rating: Optional[int] = None
    my_rating_comment: Optional[str] = None
    my_rating_created_at: Optional[datetime] = None


class BookingsListOut(BaseModel):
    bookings: List[BookingOut]


class CancelIn(BaseModel):
    reason: Optional[str] = None


class TripSeatsOut(BaseModel):
    trip_id: str
    seats_total: int
    reserved: List[int]


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


class PromoUpdateIn(BaseModel):
    percent_off_bps: Optional[int] = Field(default=None, ge=0, le=10000)
    amount_off_cents: Optional[int] = Field(default=None, ge=0)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    max_uses: Optional[int] = Field(default=None, ge=1)
    per_user_max_uses: Optional[int] = Field(default=None, ge=1)
    min_total_cents: Optional[int] = Field(default=None, ge=0)
    active: Optional[bool] = None


class VehicleIn(BaseModel):
    name: str
    seats_total: int = Field(ge=1, le=80)
    seat_columns: Optional[int] = Field(default=None, ge=1, le=5)


class VehicleOut(BaseModel):
    id: str
    name: str
    seats_total: int
    seat_columns: Optional[int] = None


class TicketOut(BaseModel):
    booking_id: str
    qr_text: str


class RateBookingIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=512)


# --- Operator admin schemas ---

class OperatorOut(BaseModel):
    id: str
    name: str
    merchant_phone: Optional[str] = None


class OperatorMemberOut(BaseModel):
    operator_id: str
    operator_name: str
    role: str


class OperatorMemberDetailOut(BaseModel):
    id: str
    user_id: str
    phone: str
    name: Optional[str] = None
    role: str
    created_at: datetime
    branch_id: Optional[str] = None
    branch_name: Optional[str] = None


class OperatorMembersListOut(BaseModel):
    members: List[OperatorMemberDetailOut]


class OperatorMemberAddIn(BaseModel):
    phone: str
    role: Optional[str] = "agent"
    branch_id: Optional[str] = None


class OperatorMemberRoleIn(BaseModel):
    role: str


class OperatorMemberBranchIn(BaseModel):
    branch_id: Optional[str] = None


class BranchIn(BaseModel):
    name: str
    commission_bps: Optional[int] = Field(default=None, ge=0, le=10000)


class BranchOut(BaseModel):
    id: str
    name: str
    commission_bps: Optional[int] = None


class WebhookIn(BaseModel):
    url: str
    secret: str
    active: bool = True


class WebhookOut(BaseModel):
    id: str
    url: str
    active: bool
    created_at: datetime


class TripCreateIn(BaseModel):
    origin: str
    destination: str
    depart_at: datetime
    arrive_at: Optional[datetime] = None
    price_cents: int
    seats_total: int = Field(ge=1, le=80)
    bus_model: Optional[str] = None
    bus_year: Optional[int] = None
    vehicle_id: Optional[str] = None


class TripUpdateIn(BaseModel):
    origin: Optional[str] = None
    destination: Optional[str] = None
    depart_at: Optional[datetime] = None
    arrive_at: Optional[datetime] = None
    price_cents: Optional[int] = Field(default=None, ge=0)
    seats_total: Optional[int] = Field(default=None, ge=1, le=80)
    bus_model: Optional[str] = None
    bus_year: Optional[int] = None
    vehicle_id: Optional[str] = None


class TripsListOut(BaseModel):
    trips: List[TripOut]


class BookingsAdminListOut(BaseModel):
    bookings: List[BookingOut]


class ReportSummaryOut(BaseModel):
    from_utc: datetime
    to_utc: datetime
    total_bookings: int
    confirmed_bookings: int
    canceled_bookings: int
    gross_revenue_cents: int
    avg_occupancy_percent: float


class TicketValidationOut(BaseModel):
    valid: bool
    reason: Optional[str] = None
    booking: Optional[BookingOut] = None


# --- Operator admin: manifests, clone, export ---

class ManifestItemOut(BaseModel):
    booking_id: str
    status: str
    seats_count: int
    seat_numbers: Optional[List[int]] = None
    user_phone: Optional[str] = None
    user_name: Optional[str] = None
    created_at: datetime


class ManifestOut(BaseModel):
    trip_id: str
    operator_name: str
    origin: str
    destination: str
    depart_at: datetime
    items: List[ManifestItemOut]


class CloneTripIn(BaseModel):
    start_date: date
    end_date: date
    weekdays: Optional[List[int]] = None  # 0=Mon .. 6=Sun; if omitted, use weekday of source trip
