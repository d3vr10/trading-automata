"""Initial schema — all tables for trading automata platform.

Revision ID: 001
Revises:
Create Date: 2026-03-08 00:00:00.000000

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
    """Create all tables."""

    # --- Authentication & Users ---

    op.create_table(
        'users',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('username', sa.String(50), unique=True, nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='user'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_users_username', 'users', ['username'])
    op.create_index('idx_users_role', 'users', ['role'])

    op.create_table(
        'broker_credentials',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('broker_type', sa.String(50), nullable=False),
        sa.Column('environment', sa.String(20), nullable=False),
        sa.Column('encrypted_api_key', sa.Text, nullable=False),
        sa.Column('encrypted_secret_key', sa.Text, nullable=False),
        sa.Column('encrypted_passphrase', sa.Text, nullable=True),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_broker_creds_user_id', 'broker_credentials', ['user_id'])

    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('used', sa.Boolean, server_default='false'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_reset_tokens_user_id', 'password_reset_tokens', ['user_id'])

    op.create_table(
        'user_settings',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'key', name='uq_user_settings_user_key'),
    )
    op.create_index('idx_user_settings_user_id', 'user_settings', ['user_id'])

    # --- Trading Tables ---

    op.execute("""
        CREATE TABLE trades (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            bot_name VARCHAR(100),
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
    op.execute("CREATE INDEX idx_trades_symbol_timestamp ON trades(symbol, entry_timestamp)")
    op.execute("CREATE INDEX idx_trades_strategy_timestamp ON trades(strategy, entry_timestamp)")
    op.execute("CREATE INDEX idx_trades_winning ON trades(is_winning_trade)")
    op.execute("CREATE INDEX idx_trades_bot_name ON trades(bot_name)")
    op.execute("CREATE INDEX idx_trades_bot_name_symbol ON trades(bot_name, symbol, entry_timestamp)")
    op.execute("CREATE INDEX idx_trades_user_id ON trades(user_id)")

    op.execute("""
        CREATE TABLE positions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            bot_name VARCHAR(100),
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
    op.execute("CREATE INDEX idx_positions_symbol ON positions(symbol)")
    op.execute("CREATE INDEX idx_positions_is_open ON positions(is_open)")
    op.execute("CREATE INDEX idx_positions_strategy ON positions(strategy)")
    op.execute("CREATE INDEX idx_positions_bot_name ON positions(bot_name)")
    op.execute("CREATE INDEX idx_positions_user_id ON positions(user_id)")

    op.execute("""
        CREATE TABLE performance_metrics (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
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
    op.execute("CREATE INDEX idx_metrics_date ON performance_metrics(metric_date)")
    op.execute("CREATE INDEX idx_metrics_strategy ON performance_metrics(strategy)")
    op.execute("CREATE INDEX idx_performance_metrics_user_id ON performance_metrics(user_id)")

    op.execute("""
        CREATE TABLE trading_events (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            bot_name VARCHAR(100),
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
    op.execute("CREATE INDEX idx_events_type ON trading_events(event_type)")
    op.execute("CREATE INDEX idx_events_severity ON trading_events(severity)")
    op.execute("CREATE INDEX idx_events_timestamp ON trading_events(event_timestamp)")
    op.execute("CREATE INDEX idx_events_bot_name ON trading_events(bot_name)")
    op.execute("CREATE INDEX idx_trading_events_user_id ON trading_events(user_id)")

    op.execute("""
        CREATE TABLE health_checks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            bot_name VARCHAR(100),
            broker VARCHAR(50) NOT NULL,
            strategy VARCHAR(100),

            is_healthy BOOLEAN NOT NULL,
            last_bar_timestamp TIMESTAMP,
            last_order_timestamp TIMESTAMP,
            connection_errors INTEGER DEFAULT 0,

            checked_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_health_broker ON health_checks(broker)")
    op.execute("CREATE INDEX idx_health_checked_at ON health_checks(checked_at)")
    op.execute("CREATE INDEX idx_health_bot_name ON health_checks(bot_name)")
    op.execute("CREATE INDEX idx_health_checks_user_id ON health_checks(user_id)")

    op.execute("""
        CREATE TABLE bot_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            bot_name VARCHAR(100),
            session_id NUMERIC NOT NULL UNIQUE,
            started_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_bot_sessions_started_at ON bot_sessions(started_at DESC)")
    op.execute("CREATE INDEX idx_sessions_bot_name ON bot_sessions(bot_name)")
    op.execute("CREATE INDEX idx_bot_sessions_user_id ON bot_sessions(user_id)")


def downgrade() -> None:
    """Drop all tables."""
    op.execute("DROP TABLE IF EXISTS bot_sessions")
    op.execute("DROP TABLE IF EXISTS health_checks")
    op.execute("DROP TABLE IF EXISTS trading_events")
    op.execute("DROP TABLE IF EXISTS performance_metrics")
    op.execute("DROP TABLE IF EXISTS positions")
    op.execute("DROP TABLE IF EXISTS trades")
    op.execute("DROP TABLE IF EXISTS user_settings")
    op.execute("DROP TABLE IF EXISTS password_reset_tokens")
    op.execute("DROP TABLE IF EXISTS broker_credentials")
    op.execute("DROP TABLE IF EXISTS users")
