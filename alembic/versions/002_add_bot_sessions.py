"""Add bot_sessions table to track session start times.

Revision ID: 002
Revises: 001
Create Date: 2026-02-17 01:15:00.000000

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
    """Create bot_sessions table for tracking bot process sessions."""

    # Bot sessions table: tracks when each bot process starts
    op.execute("""
        CREATE TABLE bot_sessions (
            id SERIAL PRIMARY KEY,
            session_id NUMERIC NOT NULL UNIQUE,
            started_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Create index for efficient lookups of latest session
    op.execute("CREATE INDEX idx_bot_sessions_started_at ON bot_sessions(started_at DESC)")


def downgrade() -> None:
    """Drop bot_sessions table."""
    op.execute("DROP TABLE IF EXISTS bot_sessions")
