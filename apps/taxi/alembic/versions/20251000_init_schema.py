"""initial schema creation

Revision ID: 20251000_init_schema
Revises: 
Create Date: 2025-10-01 00:00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '20251000_init_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create all tables from SQLAlchemy models metadata.
    # This bootstraps an empty database to the current base schema.
    # Subsequent migrations (e.g., 20251001_add_escrow) will apply incremental changes.
    bind = op.get_bind()
    # Import here to avoid Alembic import-time side effects
    from app.models import Base
    Base.metadata.create_all(bind)


def downgrade() -> None:
    # No-op for initial bootstrap; schema teardown is not supported via downgrade.
    pass

