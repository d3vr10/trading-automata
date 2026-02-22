"""Pydantic models for multi-bot orchestration configuration.

Defines the configuration schema for BotOrchestrator and individual BotInstance objects.
Supports both centralized (single bots.yaml) and distributed (bots/ directory) config modes.
"""

from typing import Literal, Optional
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator


class BrokerConfig(BaseModel):
    """Broker connection configuration."""

    type: str = Field(..., description="Broker type: 'alpaca' or 'coinbase'")
    environment: str = Field(default="paper", description="Trading environment: 'paper' or 'live'")
    api_key: str = Field(..., description="Broker API key")
    secret_key: str = Field(..., description="Broker secret key")
    passphrase: str = Field(default="", description="Broker passphrase (Coinbase only)")

    @field_validator('type')
    @classmethod
    def validate_broker_type(cls, v):
        """Validate broker type is supported."""
        if v.lower() not in ['alpaca', 'coinbase']:
            raise ValueError(f"Broker type must be 'alpaca' or 'coinbase', got '{v}'")
        return v.lower()

    @field_validator('environment')
    @classmethod
    def validate_environment(cls, v):
        """Validate trading environment."""
        if v.lower() not in ['paper', 'live']:
            raise ValueError(f"Environment must be 'paper' or 'live', got '{v}'")
        return v.lower()


class AllocationConfig(BaseModel):
    """Fund allocation configuration for the bot."""

    type: Literal["dollars", "shares"] = Field(default="dollars", description="Allocation type")
    amount: Decimal = Field(..., description="Dollar amount or share count allocated to this bot", decimal_places=2)

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        """Ensure amount is positive."""
        if v <= 0:
            raise ValueError(f"Allocation amount must be positive, got {v}")
        return v


class FenceConfig(BaseModel):
    """Virtual fence (fund compartmentalization) configuration."""

    type: Literal["hard", "soft"] = Field(
        default="hard",
        description="Hard: refuse trades exceeding allocation. Soft: warn but allow overage_pct."
    )
    overage_pct: float = Field(
        default=0.0,
        description="Allowed overage percentage (only used with soft fence). e.g., 0.05 = 5%"
    )

    @field_validator('overage_pct')
    @classmethod
    def validate_overage_pct(cls, v):
        """Ensure overage_pct is non-negative."""
        if v < 0:
            raise ValueError(f"overage_pct must be >= 0, got {v}")
        return v


class RiskConfig(BaseModel):
    """Risk management configuration per bot."""

    stop_loss_pct: float = Field(default=2.0, description="Stop loss percentage per trade")
    take_profit_pct: float = Field(default=6.0, description="Take profit percentage per trade")
    max_position_size: float = Field(default=0.1, description="Max position size as % of allocation")
    max_portfolio_risk: float = Field(default=0.02, description="Max portfolio risk as % of allocation")

    @field_validator('stop_loss_pct', 'take_profit_pct', 'max_position_size', 'max_portfolio_risk')
    @classmethod
    def validate_positive(cls, v, info):
        """Ensure all risk parameters are positive."""
        if v <= 0:
            raise ValueError(f"{info.field_name} must be positive, got {v}")
        return v

    @field_validator('take_profit_pct')
    @classmethod
    def validate_tp_gt_sl(cls, v, info):
        """Ensure take_profit > stop_loss."""
        if 'stop_loss_pct' in info.data and v <= info.data['stop_loss_pct']:
            raise ValueError(f"take_profit_pct ({v}) must be > stop_loss_pct ({info.data['stop_loss_pct']})")
        return v


class TradeFrequencyConfig(BaseModel):
    """Trade frequency and polling configuration."""

    poll_interval_minutes: int = Field(default=1, description="Bar poll interval in minutes. 1 = 1-minute bars")

    @field_validator('poll_interval_minutes')
    @classmethod
    def validate_interval(cls, v):
        """Ensure interval is positive."""
        if v < 1:
            raise ValueError(f"poll_interval_minutes must be >= 1, got {v}")
        return v


class DataProviderConfig(BaseModel):
    """Data provider configuration."""

    type: str = Field(default="alpaca", description="Data provider type: 'alpaca' (only option currently)")
    api_key: str = Field(default="", description="Data provider API key (optional if same as broker)")
    secret_key: str = Field(default="", description="Data provider secret key (optional if same as broker)")

    @field_validator('type')
    @classmethod
    def validate_type(cls, v):
        """Validate data provider type."""
        if v.lower() not in ['alpaca']:
            raise ValueError(f"Data provider type must be 'alpaca', got '{v}'")
        return v.lower()


class BotConfig(BaseModel):
    """Configuration for a single trading bot instance."""

    name: str = Field(..., description="Unique name for this bot instance")
    enabled: bool = Field(default=True, description="Whether this bot should be started")
    broker: BrokerConfig = Field(..., description="Broker connection config")
    allocation: AllocationConfig = Field(..., description="Fund allocation config")
    fence: FenceConfig = Field(default_factory=FenceConfig, description="Virtual fence config")
    risk: RiskConfig = Field(default_factory=RiskConfig, description="Risk management config")
    trade_frequency: TradeFrequencyConfig = Field(default_factory=TradeFrequencyConfig, description="Trade frequency config")
    strategy_config: str = Field(default="config/strategies.yaml", description="Path to strategy config YAML")
    data_provider: DataProviderConfig = Field(default_factory=DataProviderConfig, description="Data provider config")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Ensure name is non-empty and valid."""
        if not v or not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError(f"Bot name must be alphanumeric (with _ or -), got '{v}'")
        return v

    @field_validator('strategy_config')
    @classmethod
    def validate_strategy_config(cls, v):
        """Ensure strategy_config path is not empty."""
        if not v:
            raise ValueError("strategy_config path cannot be empty")
        return v

    @field_validator('broker')
    @classmethod
    def validate_broker_credentials(cls, v):
        """Validate broker-specific credentials."""
        if v.type == 'coinbase' and not v.passphrase:
            raise ValueError("Coinbase broker requires passphrase to be set")
        return v


class GlobalConfig(BaseModel):
    """Global configuration shared across all bots."""

    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/trading_bot",
        description="PostgreSQL connection string"
    )
    telegram_token: str = Field(default="", description="Telegram bot token")
    telegram_chat_id: str = Field(default="", description="Telegram chat ID for notifications")
    telegram_username_whitelist: str = Field(default="", description="Comma-separated usernames allowed to control bot")
    telegram_webhook_url: str = Field(default="", description="Webhook URL for Telegram updates")
    telegram_webhook_secret: str = Field(default="", description="Webhook secret for Telegram validation")
    telegram_webhook_port: int = Field(default=8080, description="Port for webhook server")
    log_level: str = Field(default="INFO", description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    log_file: Optional[str] = Field(default=None, description="Log file path (optional)")
    database_pool_size: int = Field(default=10, description="Database connection pool size")
    database_max_overflow: int = Field(default=20, description="Maximum overflow connections")
    health_check_interval: int = Field(default=300, description="Health check interval in seconds")
    use_cached_data: bool = Field(default=True, description="Whether to use cached historical data")

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}, got '{v}'")
        return v.upper()

    @field_validator('database_pool_size', 'database_max_overflow', 'health_check_interval')
    @classmethod
    def validate_positive(cls, v):
        """Ensure pool and interval settings are positive."""
        if v <= 0:
            raise ValueError(f"Value must be positive, got {v}")
        return v


class OrchestratorConfig(BaseModel):
    """Complete configuration for BotOrchestrator."""

    global_config: GlobalConfig = Field(..., description="Global shared configuration")
    bots: list[BotConfig] = Field(..., description="List of bot configurations")

    @field_validator('bots')
    @classmethod
    def validate_bots(cls, v):
        """Ensure at least one bot is defined."""
        if not v:
            raise ValueError("At least one bot configuration must be defined")
        return v

    @field_validator('bots')
    @classmethod
    def validate_unique_names(cls, v):
        """Ensure all bot names are unique."""
        names = [bot.name for bot in v]
        if len(names) != len(set(names)):
            raise ValueError("All bot names must be unique")
        return v
