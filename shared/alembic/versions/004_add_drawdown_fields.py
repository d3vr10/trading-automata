"""Add high_water_mark and drawdown_pct to portfolio_snapshots.

Revision ID: 004
Revises: 003
Create Date: 2026-03-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('portfolio_snapshots', sa.Column(
        'high_water_mark', sa.Numeric(20, 8), nullable=False, server_default='0',
    ))
    op.add_column('portfolio_snapshots', sa.Column(
        'drawdown_pct', sa.Float, nullable=False, server_default='0',
    ))


def downgrade() -> None:
    op.drop_column('portfolio_snapshots', 'drawdown_pct')
    op.drop_column('portfolio_snapshots', 'high_water_mark')
