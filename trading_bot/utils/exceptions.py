"""Custom exceptions for the trading bot."""


class TradingBotError(Exception):
    """Base exception for all trading bot errors."""
    pass


class BrokerError(TradingBotError):
    """Error from broker operations."""
    pass


class BrokerConnectionError(BrokerError):
    """Failed to connect to broker."""
    pass


class OrderExecutionError(TradingBotError):
    """Error executing an order."""
    pass


class StrategyError(TradingBotError):
    """Error in strategy execution."""
    pass


class StrategyValidationError(StrategyError):
    """Strategy configuration validation failed."""
    pass


class PortfolioError(TradingBotError):
    """Error in portfolio management."""
    pass


class InsufficientBuyingPowerError(PortfolioError):
    """Insufficient buying power for order."""
    pass


class NoPositionError(PortfolioError):
    """Position does not exist."""
    pass


class ConfigurationError(TradingBotError):
    """Configuration error."""
    pass


class DataError(TradingBotError):
    """Data fetch or processing error."""
    pass
