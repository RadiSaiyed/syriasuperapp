from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class RequestOtpIn(BaseModel):
    phone: str


class VerifyOtpIn(BaseModel):
    phone: str
    otp: str
    session_id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = Field(default=None, description="renter|seller")


class TokenOut(BaseModel):
    access_token: str


class CompanyCreateIn(BaseModel):
    name: str
    location: Optional[str] = None
    description: Optional[str] = None


class CompanyOut(BaseModel):
    id: str
    name: str
    location: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime


class VehicleCreateIn(BaseModel):
    make: str
    model: str
    year: Optional[int] = Field(None, ge=1900)
    transmission: Optional[str] = Field(None, description="auto|manual")
    seats: Optional[int] = Field(None, ge=1)
    location: Optional[str] = None
    price_per_day_cents: int = Field(..., ge=0)


class VehicleUpdateIn(BaseModel):
    transmission: Optional[str] = None
    seats: Optional[int] = Field(None, ge=1)
    location: Optional[str] = None
    price_per_day_cents: Optional[int] = Field(None, ge=0)
    status: Optional[str] = Field(None, description="available|unavailable")


class VehicleOut(BaseModel):
    id: str
    company_id: str
    make: str
    model: str
    year: Optional[int] = None
    transmission: Optional[str] = None
    seats: Optional[int] = None
    location: Optional[str] = None
    price_per_day_cents: int
    status: str
    created_at: datetime


class VehiclesListOut(BaseModel):
    vehicles: List[VehicleOut]
    total: int


class BookingCreateIn(BaseModel):
    start_date: str  # ISO date
    end_date: str


class BookingOut(BaseModel):
    id: str
    vehicle_id: str
    start_date: str
    end_date: str
    days: int
    total_cents: int
    status: str
    created_at: datetime


class BookingsListOut(BaseModel):
    bookings: List[BookingOut]


class VehicleImageCreateIn(BaseModel):
    url: str
    sort_order: int | None = 0


class VehicleImageOut(BaseModel):
    id: str
    vehicle_id: str
    url: str
    sort_order: int
    created_at: datetime


class BookedRangeOut(BaseModel):
    start_date: str
    end_date: str
