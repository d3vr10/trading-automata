"""SQLAlchemy ORM models for the API service.

These models mirror the shared database schema. The canonical schema
is defined in the Alembic migrations (shared/alembic/versions/).
"""

from datetime import datetime, UTC

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, Integer, JSON, Numeric, String, Text,
    ForeignKey, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, server_default="user")  # root, admin, user
    is_active = Column(Boolean, server_default="true")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    broker_credentials = relationship("BrokerCredential", back_populates="user", cascade="all, delete-orphan")
    bot_configurations = relationship("BotConfiguration", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSetting", back_populates="user", cascade="all, delete-orphan")


class BrokerCredential(Base):
    __tablename__ = "broker_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    broker_type = Column(String(50), nullable=False)  # alpaca, coinbase
    environment = Column(String(20), nullable=False)   # paper, live
    encrypted_api_key = Column(Text, nullable=False)
    encrypted_secret_key = Column(Text, nullable=False)
    encrypted_passphrase = Column(Text, nullable=True)  # Coinbase only
    label = Column(String(100), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="broker_credentials")


class BotConfiguration(Base):
    __tablename__ = "bot_configurations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    strategy_id = Column(String(100), nullable=False)
    credential_id = Column(Integer, ForeignKey("broker_credentials.id"), nullable=False)
    allocation = Column(Numeric(20, 2), nullable=False)
    fence_type = Column(String(20), nullable=False, server_default="hard")
    fence_overage_pct = Column(Float, nullable=False, server_default="0")
    stop_loss_pct = Column(Float, nullable=False, server_default="2.0")
    take_profit_pct = Column(Float, nullable=False, server_default="6.0")
    max_position_size = Column(Float, nullable=False, server_default="0.1")
    poll_interval_minutes = Column(Integer, nullable=False, server_default="1")
    trailing_stop = Column(Boolean, nullable=False, server_default="false")
    trailing_stop_pct = Column(Float, nullable=False, server_default="1.5")
    trailing_activation_pct = Column(Float, nullable=False, server_default="1.0")
    take_profit_targets = Column(JSON, nullable=True)  # [{"pct": 3.0, "quantity_pct": 0.5}, ...]
    is_active = Column(Boolean, server_default="false")
    desired_state = Column(String(20), nullable=False, server_default="stopped")  # stopped, running, paused
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_bot_config_user_name"),)

    user = relationship("User", back_populates="bot_configurations")
    credential = relationship("BrokerCredential")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, server_default="false")
    created_at = Column(DateTime, server_default=func.now())


class UserSetting(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("user_id", "key"),)

    user = relationship("User", back_populates="settings")


# ---- Existing trading tables (read-only from API service) ----

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    strategy = Column(String(100), nullable=False)
    broker = Column(String(50), nullable=False)
    bot_name = Column(String(100), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    entry_timestamp = Column(DateTime, nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    entry_quantity = Column(Numeric(20, 8), nullable=False)
    exit_timestamp = Column(DateTime, nullable=True)
    exit_price = Column(Numeric(20, 8), nullable=True)
    gross_pnl = Column(Numeric(20, 8), nullable=True)
    net_pnl = Column(Numeric(20, 8), nullable=True)
    pnl_percent = Column(Float, nullable=True)
    is_winning_trade = Column(Boolean, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    strategy = Column(String(100), nullable=False)
    broker = Column(String(50), nullable=False)
    bot_name = Column(String(100), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    quantity = Column(Numeric(20, 8), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    current_price = Column(Numeric(20, 8), nullable=True)
    is_open = Column(Boolean, server_default="true")
    unrealized_pnl = Column(Numeric(20, 8), nullable=True)
    realized_pnl = Column(Numeric(20, 8), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class TradingEvent(Base):
    __tablename__ = "trading_events"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), nullable=False)
    event_timestamp = Column(DateTime, nullable=False)
    severity = Column(String(20), nullable=False)
    strategy = Column(String(100), nullable=True)
    symbol = Column(String(20), nullable=True)
    broker = Column(String(50), nullable=True)
    bot_name = Column(String(100), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    message = Column(Text, nullable=False)


class HealthCheck(Base):
    __tablename__ = "health_checks"

    id = Column(Integer, primary_key=True)
    broker = Column(String(50), nullable=False)
    strategy = Column(String(100), nullable=True)
    bot_name = Column(String(100), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_healthy = Column(Boolean, nullable=False)
    checked_at = Column(DateTime, nullable=False)


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True)
    metric_date = Column(DateTime, nullable=False)
    period = Column(String(20), nullable=False)
    strategy = Column(String(100), nullable=False)
    broker = Column(String(50), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    total_trades = Column(Integer, server_default="0")
    winning_trades = Column(Integer, server_default="0")
    win_rate = Column(Float, nullable=True)
    net_profit = Column(Numeric(20, 8), server_default="0")
    profit_factor = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    portfolio_value = Column(Numeric(20, 8), nullable=True)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bot_name = Column(String(100), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    equity = Column(Numeric(20, 8), nullable=False)
    cash = Column(Numeric(20, 8), nullable=False)
    broker_type = Column(String(50), nullable=True)
    currency = Column(String(10), nullable=False, server_default="USD")
    created_at = Column(DateTime, server_default=func.now())

    high_water_mark = Column(Numeric(20, 8), nullable=False, server_default="0")
    drawdown_pct = Column(Float, nullable=False, server_default="0")

    __table_args__ = (
        UniqueConstraint("user_id", "bot_name", "snapshot_date", name="uq_portfolio_snapshot_daily"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)  # start_bot, stop_bot, create_credential, etc.
    resource_type = Column(String(50), nullable=False)  # bot, credential, user
    resource_id = Column(Integer, nullable=True)
    resource_name = Column(String(200), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
