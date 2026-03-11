"""Add desired_state column to bot_configurations for restart recovery.

Revision ID: 005
Revises: 004
Create Date: 2026-03-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add desired_state: 'stopped', 'running', 'paused'
    # Default 'stopped' — only bots explicitly started get 'running'
    op.add_column(
        'bot_configurations',
        sa.Column(
            'desired_state',
            sa.String(20),
            nullable=False,
            server_default='stopped',
        ),
    )
    # Backfill: if is_active=True, set desired_state='running'
    op.execute(
        "UPDATE bot_configurations SET desired_state = 'running' WHERE is_active = true"
    )


def downgrade() -> None:
    op.drop_column('bot_configurations', 'desired_state')
