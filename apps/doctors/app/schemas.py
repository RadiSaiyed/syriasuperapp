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
    role: Optional[str] = Field(None, description="patient|doctor")


class DoctorProfileIn(BaseModel):
    specialty: str
    city: Optional[str] = None
    clinic_name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    bio: Optional[str] = None


class DoctorOut(BaseModel):
    id: str
    user_id: str
    name: Optional[str] = None
    specialty: str
    city: Optional[str] = None
    clinic_name: Optional[str] = None
    rating_avg: Optional[float] = None
    rating_count: Optional[int] = None
    address: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    bio: Optional[str] = None


class DoctorImageCreateIn(BaseModel):
    url: str
    sort_order: int = 0


class DoctorImageOut(BaseModel):
    id: str
    url: str
    sort_order: int


class SlotCreateIn(BaseModel):
    start_time: datetime
    end_time: datetime
    price_cents: int = 0


class SlotOut(BaseModel):
    id: str
    doctor_id: str
    start_time: datetime
    end_time: datetime
    is_booked: bool
    price_cents: int


class SearchSlotsIn(BaseModel):
    doctor_id: Optional[str] = None
    city: Optional[str] = None
    specialty: Optional[str] = None
    start_time: datetime
    end_time: datetime
    limit: int = 50
    offset: int = 0


class SearchSlotOut(BaseModel):
    doctor_id: str
    doctor_name: Optional[str] = None
    specialty: str
    city: Optional[str] = None
    slot_id: str
    start_time: datetime
    end_time: datetime


class SearchSlotsOut(BaseModel):
    slots: List[SearchSlotOut]


class AppointmentCreateIn(BaseModel):
    slot_id: str


class AppointmentOut(BaseModel):
    id: str
    doctor_id: str
    patient_user_id: str
    slot_id: str
    status: str
    created_at: datetime
    price_cents: int
    payment_request_id: Optional[str] = None


class AppointmentsListOut(BaseModel):
    appointments: List[AppointmentOut]


class ReviewCreateIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1024)


class ReviewOut(BaseModel):
    id: str
    doctor_id: str
    user_id: str
    rating: int
    comment: Optional[str] = None
    created_at: datetime


class ReviewsListOut(BaseModel):
    reviews: List[ReviewOut]
