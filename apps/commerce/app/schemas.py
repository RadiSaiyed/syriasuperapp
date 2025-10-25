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


class ShopOut(BaseModel):
  id: str
  name: str
  description: Optional[str] = None


class ProductOut(BaseModel):
  id: str
  shop_id: str
  name: str
  description: Optional[str] = None
  price_cents: int
  stock_qty: int
  category: Optional[str] = None
  avg_rating: Optional[float] = None
  ratings_count: Optional[int] = None


class AddCartItemIn(BaseModel):
  product_id: str
  qty: int = Field(ge=1, le=20)


class CartItemOut(BaseModel):
  id: str
  product_id: str
  product_name: str
  price_cents: int
  qty: int
  subtotal_cents: int


class CartOut(BaseModel):
  id: str
  items: List[CartItemOut]
  total_cents: int
  applied_promo_code: Optional[str] = None
  discount_cents: Optional[int] = None
  final_total_cents: Optional[int] = None


class OrderItemOut(BaseModel):
  product_id: str
  name: str
  qty: int
  price_cents: int
  subtotal_cents: int


class OrderOut(BaseModel):
  id: str
  status: str
  shop_id: str
  total_cents: int
  shipping_name: Optional[str] = None
  shipping_phone: Optional[str] = None
  shipping_address: Optional[str] = None
  created_at: datetime
  payment_request_id: Optional[str] = None
  items: List[OrderItemOut]


class OrdersListOut(BaseModel):
  orders: List[OrderOut]


class CheckoutIn(BaseModel):
  promo_code: Optional[str] = None
  shipping_name: Optional[str] = None
  shipping_phone: Optional[str] = None
  shipping_address: Optional[str] = None


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


class ReviewIn(BaseModel):
  rating: int = Field(ge=1, le=5)
  comment: Optional[str] = None


class ReviewOut(BaseModel):
  id: str
  product_id: str
  rating: int
  comment: Optional[str]
  created_at: datetime
