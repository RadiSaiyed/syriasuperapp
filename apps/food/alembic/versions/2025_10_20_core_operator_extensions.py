"""
core operator extensions: categories, modifiers, audit, columns

Revision ID: 20251020_core
Revises: 
Create Date: 2025-10-20
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '20251020_core'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use Postgres IF NOT EXISTS for idempotency in dev
    op.execute("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS hours_json TEXT")
    op.execute("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS is_open_override BOOLEAN")
    op.execute("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS special_hours_json TEXT")
    op.execute("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS busy_mode BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS max_orders_per_hour INTEGER")

    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMP NULL")
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS preparing_at TIMESTAMP NULL")
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS out_for_delivery_at TIMESTAMP NULL")
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP NULL")
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS canceled_at TIMESTAMP NULL")
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS last_status_at TIMESTAMP NULL")
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS kds_bumped BOOLEAN DEFAULT FALSE")

    op.execute("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS packed BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS station_snapshot VARCHAR(32)")

    op.execute("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS visible BOOLEAN DEFAULT TRUE")
    op.execute("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS category_id UUID")
    op.execute("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS stock_qty INTEGER")
    op.execute("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS oos_until TIMESTAMP NULL")
    op.execute("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS station VARCHAR(32)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS menu_categories (
            id UUID PRIMARY KEY,
            restaurant_id UUID NOT NULL REFERENCES restaurants(id),
            parent_id UUID NULL REFERENCES menu_categories(id),
            name VARCHAR(128) NOT NULL,
            description VARCHAR(512) NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS modifier_groups (
            id UUID PRIMARY KEY,
            restaurant_id UUID NOT NULL REFERENCES restaurants(id),
            name VARCHAR(128) NOT NULL,
            min_choices INTEGER NOT NULL DEFAULT 0,
            max_choices INTEGER NOT NULL DEFAULT 1,
            required BOOLEAN NOT NULL DEFAULT FALSE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS modifier_options (
            id UUID PRIMARY KEY,
            group_id UUID NOT NULL REFERENCES modifier_groups(id),
            name VARCHAR(128) NOT NULL,
            price_delta_cents INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS menu_item_modifier_groups (
            id UUID PRIMARY KEY,
            menu_item_id UUID NOT NULL REFERENCES menu_items(id),
            group_id UUID NOT NULL REFERENCES modifier_groups(id),
            created_at TIMESTAMP NOT NULL,
            CONSTRAINT uq_menu_item_group UNIQUE (menu_item_id, group_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id UUID PRIMARY KEY,
            user_id UUID NULL REFERENCES users(id),
            action VARCHAR(64) NOT NULL,
            entity_type VARCHAR(64) NOT NULL,
            entity_id VARCHAR(64) NULL,
            before_json VARCHAR(4096) NULL,
            after_json VARCHAR(4096) NULL,
            created_at TIMESTAMP NOT NULL
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS webhook_deliveries (
            id UUID PRIMARY KEY,
            endpoint_id UUID NULL REFERENCES food_webhook_endpoints(id),
            event VARCHAR(128) NOT NULL,
            payload_json VARCHAR(4096) NOT NULL,
            status VARCHAR(32) NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error VARCHAR(512) NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS restaurant_stations (
            id UUID PRIMARY KEY,
            restaurant_id UUID NOT NULL REFERENCES restaurants(id),
            name VARCHAR(64) NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL
        )
        """
    )


def downgrade() -> None:
    # Non-destructive in dev; no-op downgrade
    pass
