import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


def default_uuid():
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    phone = Column(String(32), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    carts = relationship("Cart", back_populates="user")
    orders = relationship("Order", back_populates="user")


class Shop(Base):
    __tablename__ = "shops"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    name = Column(String(128), nullable=False)
    description = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    products = relationship("Product", back_populates="shop")
    orders = relationship("Order", back_populates="shop")


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(String(1024), nullable=True)
    category = Column(String(64), nullable=True)
    price_cents = Column(Integer, nullable=False)
    stock_qty = Column(Integer, nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")
    # reviews relationship declared below


class Cart(Base):
    __tablename__ = "carts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="carts")
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    cart_id = Column(UUID(as_uuid=True), ForeignKey("carts.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    qty = Column(Integer, nullable=False, default=1)

    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    status = Column(String(24), nullable=False, default="created")  # created|paid|canceled|shipped
    total_cents = Column(Integer, nullable=False, default=0)
    payment_request_id = Column(String(64), nullable=True)
    shipping_name = Column(String(128), nullable=True)
    shipping_phone = Column(String(32), nullable=True)
    shipping_address = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="orders")
    shop = relationship("Shop", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    name_snapshot = Column(String(128), nullable=False)
    price_cents_snapshot = Column(Integer, nullable=False)
    qty = Column(Integer, nullable=False)
    subtotal_cents = Column(Integer, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


class PromoCode(Base):
    __tablename__ = "promo_codes"
    __table_args__ = (
        Index("ix_commerce_promo_code", "code", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    code = Column(String(32), nullable=False, unique=True)
    percent_off_bps = Column(Integer, nullable=True)
    amount_off_cents = Column(Integer, nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    max_uses = Column(Integer, nullable=True)
    per_user_max_uses = Column(Integer, nullable=True)
    uses_count = Column(Integer, nullable=False, default=0)
    min_total_cents = Column(Integer, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PromoRedemption(Base):
    __tablename__ = "promo_redemptions"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_commerce_promo_redemption_order"),
        Index("ix_commerce_promo_redemptions_promo", "promo_code_id"),
        Index("ix_commerce_promo_redemptions_user", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    promo_code_id = Column(UUID(as_uuid=True), ForeignKey("promo_codes.id"), nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class FavoriteProduct(Base):
    __tablename__ = "favorite_products"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_fav_user_product"),
        Index("ix_fav_user", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ProductReview(Base):
    __tablename__ = "product_reviews"
    __table_args__ = (
        Index("ix_review_product", "product_id"),
        Index("ix_review_user", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1..5
    comment = Column(String(1024), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    product = relationship("Product", backref="reviews")
