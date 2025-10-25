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


class FlightOut(BaseModel):
    id: str
    airline_name: str
    origin: str
    destination: str
    depart_at: datetime
    arrive_at: Optional[datetime] = None
    price_cents: int
    seats_available: int


class SearchFlightsIn(BaseModel):
    origin: str
    destination: str
    date: date


class SearchFlightsOut(BaseModel):
    flights: List[FlightOut]


class CreateBookingIn(BaseModel):
    flight_id: str
    seats_count: int = Field(ge=1, le=6)
    seat_numbers: Optional[List[int]] = None
    promo_code: Optional[str] = None


class BookingOut(BaseModel):
    id: str
    status: str
    flight_id: str
    airline_name: str
    origin: str
    destination: str
    depart_at: datetime
    seats_count: int
    total_price_cents: int
    payment_request_id: Optional[str] = None
    seat_numbers: Optional[List[int]] = None


class BookingsListOut(BaseModel):
    bookings: List[BookingOut]


class CancelIn(BaseModel):
    reason: Optional[str] = None


class FlightSeatsOut(BaseModel):
    flight_id: str
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


class TicketOut(BaseModel):
    booking_id: str
    qr_text: str
