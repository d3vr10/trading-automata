"""Add symbols column to bot_configurations.

Revision ID: 008
Revises: 007
Create Date: 2026-03-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bot_configurations",
        sa.Column("symbols", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bot_configurations", "symbols")
