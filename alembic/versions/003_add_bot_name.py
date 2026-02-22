"""Add bot_name column to all relevant tables for multi-bot support.

Revision ID: 003
Revises: 002
Create Date: 2026-02-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add bot_name columns to support multi-bot architecture."""

    # Add bot_name to trades table
    op.add_column('trades', sa.Column('bot_name', sa.String(100), nullable=True))
    op.create_index('idx_trades_bot_name', 'trades', ['bot_name'])
    op.create_index('idx_trades_bot_name_symbol', 'trades', ['bot_name', 'symbol', 'entry_timestamp'])

    # Add bot_name to positions table
    op.add_column('positions', sa.Column('bot_name', sa.String(100), nullable=True))
    op.create_index('idx_positions_bot_name', 'positions', ['bot_name'])

    # Add bot_name to trading_events table
    op.add_column('trading_events', sa.Column('bot_name', sa.String(100), nullable=True))
    op.create_index('idx_events_bot_name', 'trading_events', ['bot_name'])

    # Add bot_name to health_checks table
    op.add_column('health_checks', sa.Column('bot_name', sa.String(100), nullable=True))
    op.create_index('idx_health_bot_name', 'health_checks', ['bot_name'])

    # Add bot_name to bot_sessions table
    op.add_column('bot_sessions', sa.Column('bot_name', sa.String(100), nullable=True))
    op.create_index('idx_sessions_bot_name', 'bot_sessions', ['bot_name'])


def downgrade() -> None:
    """Remove bot_name columns."""
    for table in ['bot_sessions', 'health_checks', 'trading_events', 'positions', 'trades']:
        op.drop_index(f'idx_{table.split("_")[0]}_bot_name', table_name=table)
        op.drop_column(table, 'bot_name')
