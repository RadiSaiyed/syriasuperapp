from alembic import op
import sqlalchemy as sa

revision = '20251010_loyalty_rewards'
down_revision = '20251006_benef_paymode'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('rider_loyalty_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('driver_loyalty_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('rides', sa.Column('rider_reward_applied', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('rides', sa.Column('driver_reward_fee_waived', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.alter_column('users', 'rider_loyalty_count', server_default=None)
    op.alter_column('users', 'driver_loyalty_count', server_default=None)
    op.alter_column('rides', 'rider_reward_applied', server_default=None)
    op.alter_column('rides', 'driver_reward_fee_waived', server_default=None)


def downgrade():
    op.drop_column('rides', 'driver_reward_fee_waived')
    op.drop_column('rides', 'rider_reward_applied')
    op.drop_column('users', 'driver_loyalty_count')
    op.drop_column('users', 'rider_loyalty_count')
