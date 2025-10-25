from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# Auth
class RequestOtpIn(BaseModel):
    phone: str


class VerifyOtpIn(BaseModel):
    phone: str
    otp: str
    session_id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = Field(default=None, description="buyer|farmer|worker")


class TokenOut(BaseModel):
    access_token: str


# Farm
class FarmCreateIn(BaseModel):
    name: str
    location: Optional[str] = None
    description: Optional[str] = None


class FarmOut(BaseModel):
    id: str
    name: str
    location: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime


# Listings
class ListingCreateIn(BaseModel):
    produce_name: str
    category: Optional[str] = None
    quantity_kg: int = Field(..., ge=0)
    price_per_kg_cents: int = Field(..., ge=0)


class ListingUpdateIn(BaseModel):
    quantity_kg: Optional[int] = Field(None, ge=0)
    price_per_kg_cents: Optional[int] = Field(None, ge=0)
    status: Optional[str] = Field(None, description="active|sold_out")


class ListingOut(BaseModel):
    id: str
    farm_id: str
    produce_name: str
    category: Optional[str] = None
    quantity_kg: int
    price_per_kg_cents: int
    status: str
    created_at: datetime


class ListingsListOut(BaseModel):
    listings: List[ListingOut]
    total: int


# Orders
class OrderCreateIn(BaseModel):
    qty_kg: int = Field(..., ge=1)


class OrderOut(BaseModel):
    id: str
    listing_id: str
    qty_kg: int
    total_cents: int
    status: str
    created_at: datetime


class OrdersListOut(BaseModel):
    orders: List[OrderOut]


# Jobs
class JobCreateIn(BaseModel):
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    wage_per_day_cents: Optional[int] = Field(None, ge=0)
    start_date: Optional[str] = Field(None, description="ISO date")
    end_date: Optional[str] = Field(None, description="ISO date")


class JobOut(BaseModel):
    id: str
    farm_id: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    wage_per_day_cents: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str
    created_at: datetime


class JobsListOut(BaseModel):
    jobs: List[JobOut]
    total: int


class ApplyIn(BaseModel):
    message: Optional[str] = None


class ApplicationOut(BaseModel):
    id: str
    job_id: str
    user_id: str
    message: Optional[str] = None
    status: str
    created_at: datetime


class ApplicationsListOut(BaseModel):
    applications: List[ApplicationOut]


class ApplicationStatusUpdateIn(BaseModel):
    status: str = Field(..., description="applied|reviewed|accepted|rejected")
