"""init bus schema

Revision ID: 2025_10_31_0001
Revises: 
Create Date: 2025-10-31 00:01:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '2025_10_31_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_users_phone'), 'users', ['phone'], unique=True)

    # operators
    op.create_table(
        'operators',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('merchant_phone', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('uq_operators_name', 'operators', ['name'], unique=True)

    # operator branches
    op.create_table(
        'bus_operator_branches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('operator_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('operators.id'), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('commission_bps', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_bus_operator_branches_operator', 'bus_operator_branches', ['operator_id'], unique=False)
    op.create_unique_constraint('uq_operator_branch_name', 'bus_operator_branches', ['operator_id', 'name'])

    # vehicles
    op.create_table(
        'bus_vehicles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('operator_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('operators.id'), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('seats_total', sa.Integer(), nullable=False),
        sa.Column('seat_columns', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_bus_vehicles_operator', 'bus_vehicles', ['operator_id'], unique=False)

    # operator members
    op.create_table(
        'operator_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('operator_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('operators.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('branch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bus_operator_branches.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_unique_constraint('uq_operator_member', 'operator_members', ['operator_id', 'user_id'])
    op.create_index('ix_operator_members_operator', 'operator_members', ['operator_id'], unique=False)
    op.create_index('ix_operator_members_user', 'operator_members', ['user_id'], unique=False)

    # trips
    op.create_table(
        'trips',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('operator_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('operators.id'), nullable=False),
        sa.Column('origin', sa.String(length=64), nullable=False),
        sa.Column('destination', sa.String(length=64), nullable=False),
        sa.Column('depart_at', sa.DateTime(), nullable=False),
        sa.Column('arrive_at', sa.DateTime(), nullable=True),
        sa.Column('price_cents', sa.Integer(), nullable=False),
        sa.Column('seats_total', sa.Integer(), nullable=False),
        sa.Column('seats_available', sa.Integer(), nullable=False),
        sa.Column('bus_model', sa.String(length=64), nullable=True),
        sa.Column('bus_year', sa.Integer(), nullable=True),
        sa.Column('vehicle_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bus_vehicles.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # bookings
    op.create_table(
        'bookings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('trip_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('trips.id'), nullable=False),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('seats_count', sa.Integer(), nullable=False),
        sa.Column('total_price_cents', sa.Integer(), nullable=False),
        sa.Column('payment_request_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('boarded_at', sa.DateTime(), nullable=True),
        sa.Column('operator_branch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bus_operator_branches.id'), nullable=True),
    )

    # trip seats
    op.create_table(
        'trip_seats',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('trip_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('trips.id'), nullable=False),
        sa.Column('seat_number', sa.Integer(), nullable=False),
        sa.Column('booking_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bookings.id'), nullable=True),
    )
    op.create_unique_constraint('uq_trip_seat', 'trip_seats', ['trip_id', 'seat_number'])
    op.create_index('ix_trip_seats_trip', 'trip_seats', ['trip_id'], unique=False)

    # promo codes
    op.create_table(
        'bus_promo_codes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('operator_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('operators.id'), nullable=True),
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('percent_off_bps', sa.Integer(), nullable=True),
        sa.Column('amount_off_cents', sa.Integer(), nullable=True),
        sa.Column('valid_from', sa.DateTime(), nullable=True),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('max_uses', sa.Integer(), nullable=True),
        sa.Column('per_user_max_uses', sa.Integer(), nullable=True),
        sa.Column('uses_count', sa.Integer(), nullable=False),
        sa.Column('min_total_cents', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_bus_promo_code', 'bus_promo_codes', ['code'], unique=True)

    # promo redemptions
    op.create_table(
        'bus_promo_redemptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('promo_code_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bus_promo_codes.id'), nullable=False),
        sa.Column('booking_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bookings.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_unique_constraint('uq_bus_promo_redemption_booking', 'bus_promo_redemptions', ['booking_id'])
    op.create_index('ix_bus_promo_redemptions_promo', 'bus_promo_redemptions', ['promo_code_id'], unique=False)
    op.create_index('ix_bus_promo_redemptions_user', 'bus_promo_redemptions', ['user_id'], unique=False)

    # operator webhooks
    op.create_table(
        'bus_operator_webhooks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('operator_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('operators.id'), nullable=False),
        sa.Column('url', sa.String(length=512), nullable=False),
        sa.Column('secret', sa.String(length=256), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_bus_operator_webhooks_operator', 'bus_operator_webhooks', ['operator_id'], unique=False)

    # trip ratings
    op.create_table(
        'trip_ratings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('booking_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bookings.id'), nullable=False),
        sa.Column('trip_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('trips.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_unique_constraint('uq_trip_ratings_booking', 'trip_ratings', ['booking_id'])
    op.create_index('ix_trip_ratings_trip', 'trip_ratings', ['trip_id'], unique=False)
    op.create_index('ix_trip_ratings_user', 'trip_ratings', ['user_id'], unique=False)


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_index('ix_trip_ratings_user', table_name='trip_ratings')
    op.drop_index('ix_trip_ratings_trip', table_name='trip_ratings')
    op.drop_constraint('uq_trip_ratings_booking', 'trip_ratings', type_='unique')
    op.drop_table('trip_ratings')

    op.drop_index('ix_bus_operator_webhooks_operator', table_name='bus_operator_webhooks')
    op.drop_table('bus_operator_webhooks')

    op.drop_index('ix_bus_promo_redemptions_user', table_name='bus_promo_redemptions')
    op.drop_index('ix_bus_promo_redemptions_promo', table_name='bus_promo_redemptions')
    op.drop_constraint('uq_bus_promo_redemption_booking', 'bus_promo_redemptions', type_='unique')
    op.drop_table('bus_promo_redemptions')

    op.drop_index('ix_bus_promo_code', table_name='bus_promo_codes')
    op.drop_table('bus_promo_codes')

    op.drop_index('ix_trip_seats_trip', table_name='trip_seats')
    op.drop_constraint('uq_trip_seat', 'trip_seats', type_='unique')
    op.drop_table('trip_seats')

    op.drop_table('bookings')

    op.drop_table('trips')

    op.drop_index('ix_operator_members_user', table_name='operator_members')
    op.drop_index('ix_operator_members_operator', table_name='operator_members')
    op.drop_constraint('uq_operator_member', 'operator_members', type_='unique')
    op.drop_table('operator_members')

    op.drop_index('ix_bus_vehicles_operator', table_name='bus_vehicles')
    op.drop_table('bus_vehicles')

    op.drop_constraint('uq_operator_branch_name', 'bus_operator_branches', type_='unique')
    op.drop_index('ix_bus_operator_branches_operator', table_name='bus_operator_branches')
    op.drop_table('bus_operator_branches')

    op.drop_index('uq_operators_name', table_name='operators')
    op.drop_table('operators')

    op.drop_index(op.f('ix_users_phone'), table_name='users')
    op.drop_table('users')

