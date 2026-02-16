import os
import yaml
import logging
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, Dict, Any
from pathlib import Path


logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings with support for config.yml and environment variable precedence.

    Settings are loaded in this order (environment variables override earlier sources):
    1. config.yml file (if exists)
    2. .env file
    3. Environment variables
    """

    # Alpaca API credentials
    alpaca_api_key: str = Field('', env='ALPACA_API_KEY')
    alpaca_secret_key: str = Field('', env='ALPACA_SECRET_KEY')

    # Coinbase API credentials
    coinbase_api_key: str = Field('', env='COINBASE_API_KEY')
    coinbase_secret_key: str = Field('', env='COINBASE_SECRET_KEY')
    coinbase_passphrase: str = Field('', env='COINBASE_PASSPHRASE')

    # Trading environment
    trading_environment: str = Field('paper', env='TRADING_ENV')

    # Broker selection
    broker: str = Field('alpaca', env='BROKER')

    # Logging configuration
    log_level: str = Field('INFO', env='LOG_LEVEL')
    log_file: Optional[str] = Field(None, env='LOG_FILE')

    # Strategy configuration
    strategy_config_path: str = Field(
        'config/strategies.yaml',
        env='STRATEGY_CONFIG_PATH'
    )

    # Config file path
    config_file_path: str = Field(
        'config/config.yml',
        env='CONFIG_FILE_PATH'
    )

    # Risk management
    max_position_size: float = Field(0.1, env='MAX_POSITION_SIZE')
    max_portfolio_risk: float = Field(0.02, env='MAX_PORTFOLIO_RISK')

    # Database configuration
    database_url: str = Field(
        'postgresql://postgres:postgres@localhost:5432/trading_bot',
        env='DATABASE_URL'
    )
    database_pool_size: int = Field(10, env='DATABASE_POOL_SIZE')
    database_max_overflow: int = Field(20, env='DATABASE_MAX_OVERFLOW')

    # Telegram bot configuration
    telegram_token: str = Field('', env='TELEGRAM_TOKEN')
    telegram_chat_id: str = Field('', env='TELEGRAM_CHAT_ID')

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False

    def validate(self) -> None:
        """Validate settings."""
        if self.trading_environment not in ('paper', 'live'):
            raise ValueError(
                f"Invalid trading_environment: {self.trading_environment}. "
                "Must be 'paper' or 'live'."
            )
        if self.max_position_size <= 0 or self.max_position_size > 1:
            raise ValueError(
                f"max_position_size must be between 0 and 1, got {self.max_position_size}"
            )
        if self.max_portfolio_risk <= 0 or self.max_portfolio_risk > 1:
            raise ValueError(
                f"max_portfolio_risk must be between 0 and 1, got {self.max_portfolio_risk}"
            )
        if not Path(self.strategy_config_path).exists():
            raise ValueError(
                f"Strategy config file not found: {self.strategy_config_path}"
            )


def _load_yaml_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file.

    Args:
        config_path: Path to YAML config file

    Returns:
        Dictionary with configuration or empty dict if file doesn't exist.
    """
    config_file = Path(config_path)

    if not config_file.exists():
        logger.debug(f"Config file not found: {config_path}")
        return {}

    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f) or {}
        logger.info(f"Loaded config from {config_path}")
        return config
    except Exception as e:
        logger.warning(f"Failed to load config from {config_path}: {e}")
        return {}


def _merge_settings(yaml_config: Dict[str, Any]) -> Dict[str, Any]:
    """Merge YAML config with environment variables.

    Environment variables have precedence over YAML config.

    Args:
        yaml_config: Configuration loaded from YAML file

    Returns:
        Merged configuration dictionary.
    """
    merged = {}

    # Start with YAML config
    if 'app' in yaml_config:
        app_config = yaml_config['app']
        if isinstance(app_config, dict):
            merged.update(app_config)

    # Map YAML keys to environment variable names
    yaml_to_env = {
        'alpaca_api_key': 'ALPACA_API_KEY',
        'alpaca_secret_key': 'ALPACA_SECRET_KEY',
        'coinbase_api_key': 'COINBASE_API_KEY',
        'coinbase_secret_key': 'COINBASE_SECRET_KEY',
        'coinbase_passphrase': 'COINBASE_PASSPHRASE',
        'trading_environment': 'TRADING_ENV',
        'broker': 'BROKER',
        'log_level': 'LOG_LEVEL',
        'log_file': 'LOG_FILE',
        'strategy_config_path': 'STRATEGY_CONFIG_PATH',
        'config_file_path': 'CONFIG_FILE_PATH',
        'max_position_size': 'MAX_POSITION_SIZE',
        'max_portfolio_risk': 'MAX_PORTFOLIO_RISK',
        'database_url': 'DATABASE_URL',
        'database_pool_size': 'DATABASE_POOL_SIZE',
        'database_max_overflow': 'DATABASE_MAX_OVERFLOW',
        'telegram_token': 'TELEGRAM_TOKEN',
        'telegram_chat_id': 'TELEGRAM_CHAT_ID',
    }

    # Override with environment variables if present
    for yaml_key, env_var in yaml_to_env.items():
        if env_var in os.environ:
            value = os.environ[env_var]
            # Convert string values to appropriate types
            if yaml_key in ('max_position_size', 'max_portfolio_risk'):
                try:
                    merged[yaml_key] = float(value)
                except ValueError:
                    merged[yaml_key] = value
            else:
                merged[yaml_key] = value
            logger.debug(f"Loaded {yaml_key} from environment variable {env_var}")
        elif yaml_key not in merged:
            # Use default if not in YAML or environment
            logger.debug(f"Using default for {yaml_key}")

    return merged


def load_settings() -> Settings:
    """Load and validate application settings.

    Settings are loaded with the following precedence:
    1. config.yml file (lowest priority)
    2. .env file
    3. Environment variables (highest priority)

    Returns:
        Settings object with all configuration.

    Raises:
        ValueError: If settings are invalid or required fields are missing.
    """
    # Load YAML config file if it exists
    config_file_path = os.environ.get('CONFIG_FILE_PATH', 'config/config.yml')
    yaml_config = _load_yaml_config(config_file_path)

    # Merge YAML config with environment variables (env vars have precedence)
    merged_config = _merge_settings(yaml_config)

    # Create settings object
    # Pydantic will load .env automatically and merge with our merged_config
    settings = Settings(**merged_config)
    settings.validate()

    logger.info("Settings loaded successfully")
    return settings
