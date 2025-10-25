from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
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
    totp: Optional[str] = None


class RestaurantOut(BaseModel):
    id: str
    name: str
    city: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    rating_avg: Optional[float] = None
    rating_count: Optional[int] = None
    is_open: Optional[bool] = None
    hours: Optional[Dict[str, Any]] = None


class RestaurantImageCreateIn(BaseModel):
    url: str
    sort_order: int = 0


class RestaurantImageOut(BaseModel):
    id: str
    url: str
    sort_order: int


class MenuItemOut(BaseModel):
    id: str
    restaurant_id: str
    name: str
    description: Optional[str] = None
    price_cents: int
    available: Optional[bool] = None
    visible: Optional[bool] = None
    category_id: Optional[str] = None
    stock_qty: Optional[int] = None
    oos_until: Optional[datetime] = None
    station: Optional[str] = None


class AddCartItemIn(BaseModel):
    menu_item_id: str
    qty: int = Field(ge=1, le=20)


class CartItemOut(BaseModel):
    id: str
    menu_item_id: str
    name: str
    price_cents: int
    qty: int
    subtotal_cents: int


class CartOut(BaseModel):
    id: str
    items: List[CartItemOut]
    total_cents: int


class OrderItemOut(BaseModel):
    menu_item_id: str
    name: str
    qty: int
    price_cents: int
    subtotal_cents: int


class OrderOut(BaseModel):
    id: str
    status: str
    restaurant_id: str
    total_cents: int
    delivery_address: Optional[str] = None
    created_at: datetime
    payment_request_id: Optional[str] = None
    items: List[OrderItemOut]


class OrdersListOut(BaseModel):
    orders: List[OrderOut]


class TrackingUpdateIn(BaseModel):
    lat: float
    lon: float


class TrackingOut(BaseModel):
    lat: float
    lon: float
    updated_at: datetime | None = None


class ReviewCreateIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1024)


class ReviewOut(BaseModel):
    id: str
    restaurant_id: str
    user_id: str
    rating: int
    comment: Optional[str]
    created_at: datetime


class ReviewsListOut(BaseModel):
    reviews: List[ReviewOut]


class RestaurantHoursIn(BaseModel):
    hours: Dict[str, Any]


class CategoryIn(BaseModel):
    name: str
    parent_id: Optional[str] = None
    description: Optional[str] = None
    sort_order: int = 0


class CategoryOut(BaseModel):
    id: str
    name: str
    parent_id: Optional[str] = None
    description: Optional[str] = None
    sort_order: int


class ModifierGroupIn(BaseModel):
    name: str
    min_choices: int = 0
    max_choices: int = 1
    required: bool = False
    sort_order: int = 0


class ModifierGroupOut(BaseModel):
    id: str
    name: str
    min_choices: int
    max_choices: int
    required: bool
    sort_order: int


class ModifierOptionIn(BaseModel):
    name: str
    price_delta_cents: int = 0
    sort_order: int = 0


class ModifierOptionOut(BaseModel):
    id: str
    name: str
    price_delta_cents: int
    sort_order: int
