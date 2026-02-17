"""Database models for trading bot.

Stores trades, positions, events, and performance metrics.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column, String, Float, DateTime, Integer, Boolean,
    Numeric, Text, create_engine, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

Base = declarative_base()


class Trade(Base):
    """Represents a completed trade (entry + exit)."""

    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Trade identification
    symbol = Column(String(20), nullable=False, index=True)
    strategy = Column(String(100), nullable=False, index=True)
    broker = Column(String(50), nullable=False)

    # Entry details
    entry_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

    # Position details
    quantity = Column(Numeric(20, 8), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    current_price = Column(Numeric(20, 8), nullable=True)

    # Status
    is_open = Column(Boolean, default=True, index=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    # Performance
    unrealized_pnl = Column(Numeric(20, 8), nullable=True)
    realized_pnl = Column(Numeric(20, 8), nullable=True)

    # Metadata
    stop_loss = Column(Numeric(20, 8), nullable=True)
    take_profit = Column(Numeric(20, 8), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PerformanceMetric(Base):
    """Daily/hourly performance snapshots."""

    __tablename__ = 'performance_metrics'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Time period
    metric_date = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
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

    created_at = Column(DateTime, default=datetime.utcnow)


class TradingEvent(Base):
    """Log of significant events (alerts, errors, status changes)."""

    __tablename__ = 'trading_events'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Event details
    event_type = Column(String(50), nullable=False, index=True)  # 'trade', 'error', 'alert', 'connection'
    event_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    severity = Column(String(20), nullable=False)  # 'info', 'warning', 'error', 'critical'

    # Context
    strategy = Column(String(100), nullable=True)
    symbol = Column(String(20), nullable=True)
    broker = Column(String(50), nullable=True)

    # Details
    message = Column(Text, nullable=False)
    details = Column(Text, nullable=True)  # JSON or detailed info

    # Status
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

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
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    delivery_status = Column(String(20), default='pending')  # 'sent', 'failed', 'pending'
    error_message = Column(Text, nullable=True)

    # Context
    strategy = Column(String(100), nullable=True)
    symbol = Column(String(20), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class DatabaseConnection:
    """Manages database connections and sessions."""

    def __init__(self, database_url: str):
        """Initialize database connection.

        Args:
            database_url: PostgreSQL connection string
                e.g., postgresql://user:password@localhost:5432/trading_bot
        """
        self.engine = create_engine(
            database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Test connections before using
        )
        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self) -> None:
        """Create all tables in database."""
        Base.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    def close(self) -> None:
        """Close database connection."""
        self.engine.dispose()
