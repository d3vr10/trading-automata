"""Add trailing stop and multi-TP target columns to bot_configurations.

Revision ID: 006
Revises: 005
Create Date: 2026-03-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bot_configurations", sa.Column("trailing_stop", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("bot_configurations", sa.Column("trailing_stop_pct", sa.Float(), nullable=False, server_default="1.5"))
    op.add_column("bot_configurations", sa.Column("trailing_activation_pct", sa.Float(), nullable=False, server_default="1.0"))
    op.add_column("bot_configurations", sa.Column("take_profit_targets", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("bot_configurations", "take_profit_targets")
    op.drop_column("bot_configurations", "trailing_activation_pct")
    op.drop_column("bot_configurations", "trailing_stop_pct")
    op.drop_column("bot_configurations", "trailing_stop")
