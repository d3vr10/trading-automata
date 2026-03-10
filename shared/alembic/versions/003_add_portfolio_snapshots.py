"""Add portfolio_snapshots table for historical portfolio tracking.

Revision ID: 003
Revises: 002
Create Date: 2026-03-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'portfolio_snapshots',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('bot_name', sa.String(100), nullable=False),
        sa.Column('snapshot_date', sa.Date, nullable=False),
        sa.Column('equity', sa.Numeric(20, 8), nullable=False),
        sa.Column('cash', sa.Numeric(20, 8), nullable=False),
        sa.Column('broker_type', sa.String(50), nullable=True),
        sa.Column('currency', sa.String(10), nullable=False, server_default='USD'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'bot_name', 'snapshot_date', name='uq_portfolio_snapshot_daily'),
    )
    op.create_index('idx_portfolio_snapshot_user_date', 'portfolio_snapshots', ['user_id', 'snapshot_date'])


def downgrade() -> None:
    op.drop_table('portfolio_snapshots')
