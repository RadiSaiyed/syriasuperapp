import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Float, UniqueConstraint
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
    totp_secret = Column(String(64), nullable=True)
    twofa_enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    carts = relationship("Cart", back_populates="user")
    orders = relationship("Order", back_populates="user", foreign_keys="Order.user_id")
    # Operator membership (platform-level)
    operator_memberships = relationship("OperatorMember", back_populates="user")


class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    name = Column(String(128), nullable=False)
    city = Column(String(64), nullable=True)
    description = Column(String(512), nullable=True)
    address = Column(String(256), nullable=True)
    # Optional opening hours JSON, format per-day arrays of ["HH:MM","HH:MM"] intervals
    # Example: {"mon": [["09:00","18:00"]], "tue": [], ...}
    hours_json = Column(String(4096), nullable=True)
    special_hours_json = Column(String(4096), nullable=True)
    # Optional manual override; if set to true/false it forces is_open regardless of hours
    is_open_override = Column(Boolean, nullable=True)
    busy_mode = Column(Boolean, nullable=False, default=False)
    max_orders_per_hour = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    items = relationship("MenuItem", back_populates="restaurant")
    orders = relationship("Order", back_populates="restaurant")


class OperatorMember(Base):
    __tablename__ = "food_operator_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(String(32), nullable=False, default="admin")  # admin|agent
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="operator_memberships")


class RestaurantImage(Base):
    __tablename__ = "restaurant_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False)
    url = Column(String(1024), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class RestaurantStation(Base):
    __tablename__ = "restaurant_stations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False)
    name = Column(String(64), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(String(1024), nullable=True)
    price_cents = Column(Integer, nullable=False)
    available = Column(Boolean, nullable=False, default=True)
    visible = Column(Boolean, nullable=False, default=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("menu_categories.id"), nullable=True)
    stock_qty = Column(Integer, nullable=True)
    oos_until = Column(DateTime, nullable=True)
    station = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    restaurant = relationship("Restaurant", back_populates="items")


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
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id"), nullable=False)
    qty = Column(Integer, nullable=False, default=1)

    cart = relationship("Cart", back_populates="items")
    menu_item = relationship("MenuItem")


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False)
    status = Column(String(24), nullable=False, default="created")  # created|accepted|preparing|out_for_delivery|delivered|canceled
    total_cents = Column(Integer, nullable=False, default=0)
    delivery_address = Column(String(256), nullable=True)
    payment_request_id = Column(String(64), nullable=True)
    payment_transfer_id = Column(String(64), nullable=True)
    refund_status = Column(String(16), nullable=True)  # requested|completed
    courier_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    courier_lat = Column(Float, nullable=True)
    courier_lon = Column(Float, nullable=True)
    courier_loc_updated_at = Column(DateTime, nullable=True)
    # Status timeline (optional, for SLA/reporting)
    accepted_at = Column(DateTime, nullable=True)
    preparing_at = Column(DateTime, nullable=True)
    out_for_delivery_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    last_status_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="orders", foreign_keys=[user_id])
    restaurant = relationship("Restaurant", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    kds_bumped = Column(Boolean, nullable=False, default=False)


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id"), nullable=False)
    name_snapshot = Column(String(128), nullable=False)
    price_cents_snapshot = Column(Integer, nullable=False)
    qty = Column(Integer, nullable=False)
    subtotal_cents = Column(Integer, nullable=False)
    packed = Column(Boolean, nullable=False, default=False)
    station_snapshot = Column(String(32), nullable=True)

    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem")


class RestaurantReview(Base):
    __tablename__ = "restaurant_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False, default=5)
    comment = Column(String(1024), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class FavoriteRestaurant(Base):
    __tablename__ = "favorite_restaurants"
    __table_args__ = (
        UniqueConstraint("user_id", "restaurant_id", name="uq_fav_rest_user_rest"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class WebhookEndpoint(Base):
    __tablename__ = "food_webhook_endpoints"
    __table_args__ = (
        UniqueConstraint("url", name="uq_food_webhook_url"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    url = Column(String(512), nullable=False)
    secret = Column(String(128), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("menu_categories.id"), nullable=True)
    name = Column(String(128), nullable=False)
    description = Column(String(512), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ModifierGroup(Base):
    __tablename__ = "modifier_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False)
    name = Column(String(128), nullable=False)
    min_choices = Column(Integer, nullable=False, default=0)
    max_choices = Column(Integer, nullable=False, default=1)
    required = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ModifierOption(Base):
    __tablename__ = "modifier_options"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    group_id = Column(UUID(as_uuid=True), ForeignKey("modifier_groups.id"), nullable=False)
    name = Column(String(128), nullable=False)
    price_delta_cents = Column(Integer, nullable=False, default=0)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MenuItemModifierGroup(Base):
    __tablename__ = "menu_item_modifier_groups"
    __table_args__ = (
        UniqueConstraint("menu_item_id", "group_id", name="uq_menu_item_group"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id"), nullable=False)
    group_id = Column(UUID(as_uuid=True), ForeignKey("modifier_groups.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(64), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=True)
    before_json = Column(String(4096), nullable=True)
    after_json = Column(String(4096), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    endpoint_id = Column(UUID(as_uuid=True), ForeignKey("food_webhook_endpoints.id"), nullable=True)
    event = Column(String(128), nullable=False)
    payload_json = Column(String(4096), nullable=False)
    status = Column(String(32), nullable=False, default="pending")  # pending|sent|failed
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
