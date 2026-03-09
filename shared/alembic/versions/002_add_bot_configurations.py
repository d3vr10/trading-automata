"""Add bot_configurations table for on-demand bot creation.

Revision ID: 002
Revises: 001
Create Date: 2026-03-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bot_configurations',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('strategy_id', sa.String(100), nullable=False),
        sa.Column('credential_id', sa.Integer, sa.ForeignKey('broker_credentials.id'), nullable=False),
        sa.Column('allocation', sa.Numeric(20, 2), nullable=False),
        sa.Column('fence_type', sa.String(20), nullable=False, server_default='hard'),
        sa.Column('fence_overage_pct', sa.Float, nullable=False, server_default='0'),
        sa.Column('stop_loss_pct', sa.Float, nullable=False, server_default='2.0'),
        sa.Column('take_profit_pct', sa.Float, nullable=False, server_default='6.0'),
        sa.Column('max_position_size', sa.Float, nullable=False, server_default='0.1'),
        sa.Column('poll_interval_minutes', sa.Integer, nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean, server_default='false'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'name', name='uq_bot_config_user_name'),
    )
    op.create_index('idx_bot_config_user_id', 'bot_configurations', ['user_id'])


def downgrade() -> None:
    op.drop_table('bot_configurations')
