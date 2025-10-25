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
    role: Optional[str] = Field(default=None, description="buyer|seller")


class TokenOut(BaseModel):
    access_token: str


class RanchCreateIn(BaseModel):
    name: str
    location: Optional[str] = None
    description: Optional[str] = None


class RanchOut(BaseModel):
    id: str
    name: str
    location: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime


class AnimalCreateIn(BaseModel):
    species: str
    breed: Optional[str] = None
    sex: Optional[str] = None
    age_months: Optional[int] = Field(None, ge=0)
    weight_kg: Optional[int] = Field(None, ge=0)
    price_cents: int = Field(..., ge=0)


class AnimalUpdateIn(BaseModel):
    breed: Optional[str] = None
    sex: Optional[str] = None
    age_months: Optional[int] = Field(None, ge=0)
    weight_kg: Optional[int] = Field(None, ge=0)
    price_cents: Optional[int] = Field(None, ge=0)
    status: Optional[str] = Field(None, description="available|sold")


class AnimalOut(BaseModel):
    id: str
    ranch_id: str
    species: str
    breed: Optional[str] = None
    sex: Optional[str] = None
    age_months: Optional[int] = None
    weight_kg: Optional[int] = None
    price_cents: int
    status: str
    created_at: datetime


class AnimalsListOut(BaseModel):
    animals: List[AnimalOut]
    total: int


class ProductCreateIn(BaseModel):
    product_type: str
    unit: str = Field(default="kg")
    quantity: int = Field(..., ge=0)
    price_per_unit_cents: int = Field(..., ge=0)


class ProductUpdateIn(BaseModel):
    unit: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=0)
    price_per_unit_cents: Optional[int] = Field(None, ge=0)
    status: Optional[str] = Field(None, description="active|sold_out")


class ProductOut(BaseModel):
    id: str
    ranch_id: str
    product_type: str
    unit: str
    quantity: int
    price_per_unit_cents: int
    status: str
    created_at: datetime


class ProductsListOut(BaseModel):
    products: List[ProductOut]
    total: int


class OrderCreateIn(BaseModel):
    qty: int = Field(..., ge=1)


class OrderOut(BaseModel):
    id: str
    type: str
    product_id: Optional[str] = None
    animal_id: Optional[str] = None
    qty: int
    total_cents: int
    status: str
    created_at: datetime


class OrdersListOut(BaseModel):
    orders: List[OrderOut]


# Auctions
class AuctionCreateIn(BaseModel):
    animal_id: str
    starting_price_cents: int = Field(..., ge=0)
    ends_at_iso: str = Field(..., description="ISO8601 datetime (UTC)")


class AuctionOut(BaseModel):
    id: str
    animal_id: str
    ranch_id: str
    starting_price_cents: int
    current_price_cents: int
    highest_bid_user_id: Optional[str] = None
    ends_at: datetime
    status: str
    created_at: datetime


class AuctionsListOut(BaseModel):
    auctions: List[AuctionOut]
    total: int


class BidIn(BaseModel):
    amount_cents: int = Field(..., ge=1)
