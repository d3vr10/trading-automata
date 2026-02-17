import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(level: str = 'INFO', log_file: Optional[str] = None) -> logging.Logger:
    """Setup structured logging for the trading bot.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to log to

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger('trading_bot')
    logger.setLevel(getattr(logging, level.upper()))

    # Remove any existing handlers
    logger.handlers.clear()

    # Console handler with INFO level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler (optional) with DEBUG level for detailed logging
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance.
    """
    return logging.getLogger(f'trading_bot.{name}')
