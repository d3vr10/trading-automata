"""Database module for trading bot.

Simple PostgreSQL integration using raw psycopg3 + Pydantic.
No ORM overhead, API-ready architecture.
"""

from trading_bot.database.repository import TradeRepository
from trading_bot.database.health import HealthCheckManager, HealthCheckRegistry

__all__ = [
    "TradeRepository",
    "HealthCheckManager",
    "HealthCheckRegistry",
]
