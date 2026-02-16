"""Initial schema creation for trading bot.

Revision ID: 001
Revises:
Create Date: 2026-02-15 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial schema."""

    # Trades table: stores entry and exit information
    op.execute("""
        CREATE TABLE trades (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            strategy VARCHAR(100) NOT NULL,
            broker VARCHAR(50) NOT NULL,

            -- Entry details
            entry_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
            entry_price NUMERIC(20, 8) NOT NULL,
            entry_quantity NUMERIC(20, 8) NOT NULL,
            entry_order_id VARCHAR(100) UNIQUE,

            -- Exit details
            exit_timestamp TIMESTAMP,
            exit_price NUMERIC(20, 8),
            exit_quantity NUMERIC(20, 8),
            exit_order_id VARCHAR(100) UNIQUE,

            -- Performance
            gross_pnl NUMERIC(20, 8),
            net_pnl NUMERIC(20, 8),
            pnl_percent FLOAT,
            hold_duration_seconds INTEGER,
            is_winning_trade BOOLEAN,

            -- Fees & costs
            entry_fee NUMERIC(20, 8) DEFAULT 0,
            exit_fee NUMERIC(20, 8) DEFAULT 0,
            slippage NUMERIC(20, 8) DEFAULT 0,

            -- Metadata
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Create indexes for trades table
    op.execute("CREATE INDEX idx_trades_symbol_timestamp ON trades(symbol, entry_timestamp)")
    op.execute("CREATE INDEX idx_trades_strategy_timestamp ON trades(strategy, entry_timestamp)")
    op.execute("CREATE INDEX idx_trades_winning ON trades(is_winning_trade)")

    # Positions table: tracks current positions
    op.execute("""
        CREATE TABLE positions (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            strategy VARCHAR(100) NOT NULL,
            broker VARCHAR(50) NOT NULL,

            quantity NUMERIC(20, 8) NOT NULL,
            entry_price NUMERIC(20, 8) NOT NULL,
            current_price NUMERIC(20, 8),

            is_open BOOLEAN DEFAULT true,
            opened_at TIMESTAMP DEFAULT NOW(),
            closed_at TIMESTAMP,

            unrealized_pnl NUMERIC(20, 8),
            realized_pnl NUMERIC(20, 8),

            stop_loss NUMERIC(20, 8),
            take_profit NUMERIC(20, 8),

            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Create indexes for positions table
    op.execute("CREATE INDEX idx_positions_symbol ON positions(symbol)")
    op.execute("CREATE INDEX idx_positions_is_open ON positions(is_open)")
    op.execute("CREATE INDEX idx_positions_strategy ON positions(strategy)")

    # Performance metrics table: daily/hourly snapshots
    op.execute("""
        CREATE TABLE performance_metrics (
            id SERIAL PRIMARY KEY,
            metric_date TIMESTAMP NOT NULL DEFAULT NOW(),
            period VARCHAR(20) NOT NULL,

            strategy VARCHAR(100) NOT NULL,
            broker VARCHAR(50) NOT NULL,

            total_trades INTEGER DEFAULT 0,
            winning_trades INTEGER DEFAULT 0,
            losing_trades INTEGER DEFAULT 0,
            win_rate FLOAT,

            gross_profit NUMERIC(20, 8) DEFAULT 0,
            gross_loss NUMERIC(20, 8) DEFAULT 0,
            net_profit NUMERIC(20, 8) DEFAULT 0,
            profit_factor FLOAT,

            max_consecutive_losses INTEGER DEFAULT 0,
            max_consecutive_wins INTEGER DEFAULT 0,
            max_drawdown FLOAT,
            sharpe_ratio FLOAT,

            portfolio_value NUMERIC(20, 8),
            portfolio_return_percent FLOAT,

            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Create indexes for performance_metrics table
    op.execute("CREATE INDEX idx_metrics_date ON performance_metrics(metric_date)")
    op.execute("CREATE INDEX idx_metrics_strategy ON performance_metrics(strategy)")

    # Trading events table: log significant events
    op.execute("""
        CREATE TABLE trading_events (
            id SERIAL PRIMARY KEY,
            event_type VARCHAR(50) NOT NULL,
            event_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
            severity VARCHAR(20) NOT NULL,

            strategy VARCHAR(100),
            symbol VARCHAR(20),
            broker VARCHAR(50),

            message TEXT NOT NULL,
            details TEXT,

            resolved BOOLEAN DEFAULT false,
            resolved_at TIMESTAMP,

            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Create indexes for trading_events table
    op.execute("CREATE INDEX idx_events_type ON trading_events(event_type)")
    op.execute("CREATE INDEX idx_events_severity ON trading_events(severity)")
    op.execute("CREATE INDEX idx_events_timestamp ON trading_events(event_timestamp)")

    # Health checks table: bot status monitoring
    op.execute("""
        CREATE TABLE health_checks (
            id SERIAL PRIMARY KEY,
            broker VARCHAR(50) NOT NULL,
            strategy VARCHAR(100),

            is_healthy BOOLEAN NOT NULL,
            last_bar_timestamp TIMESTAMP,
            last_order_timestamp TIMESTAMP,
            connection_errors INTEGER DEFAULT 0,

            checked_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    # Create indexes for health_checks table
    op.execute("CREATE INDEX idx_health_broker ON health_checks(broker)")
    op.execute("CREATE INDEX idx_health_checked_at ON health_checks(checked_at)")


def downgrade() -> None:
    """Drop all tables."""
    op.execute("DROP TABLE IF EXISTS health_checks")
    op.execute("DROP TABLE IF EXISTS trading_events")
    op.execute("DROP TABLE IF EXISTS performance_metrics")
    op.execute("DROP TABLE IF EXISTS positions")
    op.execute("DROP TABLE IF EXISTS trades")
