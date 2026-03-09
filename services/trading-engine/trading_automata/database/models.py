"""Database models for trading bot.

Stores trades, positions, events, and performance metrics.
"""

from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column, String, Float, DateTime, Integer, Boolean,
    Numeric, Text, Index, event
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Trade(Base):
    """Represents a completed trade (entry + exit)."""

    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Trade identification
    symbol = Column(String(20), nullable=False, index=True)
    strategy = Column(String(100), nullable=False, index=True)
    broker = Column(String(50), nullable=False)
    bot_name = Column(String(100), nullable=True, index=True)

    # Entry details
    entry_timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
    entry_price = Column(Numeric(20, 8), nullable=False)
    entry_quantity = Column(Numeric(20, 8), nullable=False)
    entry_order_id = Column(String(100), unique=True)

    # Exit details
    exit_timestamp = Column(DateTime, nullable=True)
    exit_price = Column(Numeric(20, 8), nullable=True)
    exit_quantity = Column(Numeric(20, 8), nullable=True)
    exit_order_id = Column(String(100), unique=True)

    # Performance metrics
    gross_pnl = Column(Numeric(20, 8), nullable=True)  # Profit/loss in currency
    net_pnl = Column(Numeric(20, 8), nullable=True)   # After fees
    pnl_percent = Column(Float, nullable=True)        # Return percentage

    # Trade characteristics
    hold_duration_seconds = Column(Integer, nullable=True)  # How long held
    is_winning_trade = Column(Boolean, nullable=True)       # Win/loss

    # Fees & costs
    entry_fee = Column(Numeric(20, 8), default=0)
    exit_fee = Column(Numeric(20, 8), default=0)
    slippage = Column(Numeric(20, 8), default=0)

    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Indexes for common queries
    __table_args__ = (
        Index('idx_symbol_timestamp', 'symbol', 'entry_timestamp'),
        Index('idx_strategy_timestamp', 'strategy', 'entry_timestamp'),
        Index('idx_winning_trades', 'is_winning_trade'),
    )


class Position(Base):
    """Represents current or closed positions."""

    __tablename__ = 'positions'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Position identification
    symbol = Column(String(20), nullable=False, index=True)
    strategy = Column(String(100), nullable=False)
    broker = Column(String(50), nullable=False)
    bot_name = Column(String(100), nullable=True, index=True)

    # Position details
    quantity = Column(Numeric(20, 8), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    current_price = Column(Numeric(20, 8), nullable=True)

    # Status
    is_open = Column(Boolean, default=True, index=True)
    opened_at = Column(DateTime, default=lambda: datetime.now(UTC))
    closed_at = Column(DateTime, nullable=True)

    # Performance
    unrealized_pnl = Column(Numeric(20, 8), nullable=True)
    realized_pnl = Column(Numeric(20, 8), nullable=True)

    # Metadata
    stop_loss = Column(Numeric(20, 8), nullable=True)
    take_profit = Column(Numeric(20, 8), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class PerformanceMetric(Base):
    """Daily/hourly performance snapshots."""

    __tablename__ = 'performance_metrics'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Time period
    metric_date = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
    period = Column(String(20), nullable=False)  # 'hourly', 'daily', 'weekly'

    # Strategy & broker
    strategy = Column(String(100), nullable=False, index=True)
    broker = Column(String(50), nullable=False)

    # Trade counts
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, nullable=True)

    # Profit metrics
    gross_profit = Column(Numeric(20, 8), default=0)
    gross_loss = Column(Numeric(20, 8), default=0)
    net_profit = Column(Numeric(20, 8), default=0)
    profit_factor = Column(Float, nullable=True)  # Profit / Loss

    # Risk metrics
    max_consecutive_losses = Column(Integer, default=0)
    max_consecutive_wins = Column(Integer, default=0)
    max_drawdown = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)

    # Portfolio
    portfolio_value = Column(Numeric(20, 8), nullable=True)
    portfolio_return_percent = Column(Float, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class TradingEvent(Base):
    """Log of significant events (alerts, errors, status changes)."""

    __tablename__ = 'trading_events'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Event details
    event_type = Column(String(50), nullable=False, index=True)  # 'trade', 'error', 'alert', 'connection'
    event_timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
    severity = Column(String(20), nullable=False)  # 'info', 'warning', 'error', 'critical'

    # Context
    strategy = Column(String(100), nullable=True)
    symbol = Column(String(20), nullable=True)
    broker = Column(String(50), nullable=True)
    bot_name = Column(String(100), nullable=True, index=True)

    # Details
    message = Column(Text, nullable=False)
    details = Column(Text, nullable=True)  # JSON or detailed info

    # Status
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # Indexes
    __table_args__ = (
        Index('idx_event_type_timestamp', 'event_type', 'event_timestamp'),
        Index('idx_severity_timestamp', 'severity', 'event_timestamp'),
    )


class AlertLog(Base):
    """Log of sent alerts (email, Slack, etc.)."""

    __tablename__ = 'alert_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Alert identification
    alert_type = Column(String(50), nullable=False)  # 'trade', 'loss', 'error', 'status'
    channel = Column(String(50), nullable=False)     # 'email', 'slack'

    # Content
    recipient = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=True)
    message = Column(Text, nullable=False)

    # Status
    sent_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    delivery_status = Column(String(20), default='pending')  # 'sent', 'failed', 'pending'
    error_message = Column(Text, nullable=True)

    # Context
    strategy = Column(String(100), nullable=True)
    symbol = Column(String(20), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class BotSession(Base):
    """Tracks bot process start times for uptime calculation."""

    __tablename__ = 'bot_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Numeric, nullable=False, unique=True)
    started_at = Column(DateTime, nullable=False)
    bot_name = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index('idx_bot_sessions_started_at', 'started_at'),
    )


class HealthCheck(Base):
    """Bot health monitoring and connection status."""

    __tablename__ = 'health_checks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    broker = Column(String(50), nullable=False, index=True)
    strategy = Column(String(100), nullable=True)
    bot_name = Column(String(100), nullable=True, index=True)
    is_healthy = Column(Boolean, nullable=False)
    last_bar_timestamp = Column(DateTime, nullable=True)
    last_order_timestamp = Column(DateTime, nullable=True)
    connection_errors = Column(Integer, default=0)
    checked_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)

    __table_args__ = (
        Index('idx_health_broker_strategy', 'broker', 'strategy'),
    )


class DatabaseConnection:
    """Manages async database connections and sessions."""

    def __init__(
        self,
        database_url: str,
        pool_size: int = 10,
        max_overflow: int = 20,
    ):
        """Initialize async database connection.

        Args:
            database_url: PostgreSQL connection string
                e.g., postgresql://user:password@localhost:5432/trading_automata
            pool_size: Number of connections to keep in pool (default 10)
            max_overflow: Maximum overflow connections (default 20)
        """
        # Convert postgresql:// to postgresql+psycopg:// for psycopg3 driver
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)

        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,  # Test connections before using
            connect_args={"connect_timeout": 30},  # Connection timeout (psycopg3)
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def create_tables(self) -> None:
        """Create all tables in database."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        """Close all connections in pool."""
        await self.engine.dispose()
