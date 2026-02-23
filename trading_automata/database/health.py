"""Health check and reconnection monitoring for the trading bot.

Monitors broker connectivity, data provider health, and provides
auto-reconnect logic with exponential backoff.
"""

import asyncio
import logging
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trading_automata.database.models import HealthCheck

logger = logging.getLogger(__name__)


class HealthCheckManager:
    """Manages bot health monitoring and reconnection logic.

    Tracks:
    - Broker connection status
    - Last bar received timestamp (detects stale data)
    - Last order timestamp
    - Connection error counts
    - Reconnection attempts with exponential backoff
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        broker: str,
        strategy: str,
        bot_name: Optional[str] = None,
    ):
        """Initialize health check manager.

        Args:
            session_factory: Async sessionmaker factory
            broker: Broker name (alpaca, coinbase, etc.)
            strategy: Strategy being monitored
            bot_name: Optional bot instance name (for multi-bot tracking)
        """
        self.session_factory = session_factory
        self.bot_name = bot_name or ""
        self.broker = broker
        self.strategy = strategy

        # Health tracking
        self.is_healthy = True
        self.last_bar_timestamp: Optional[datetime] = None
        self.last_order_timestamp: Optional[datetime] = None
        self.connection_errors = 0
        self.last_check = datetime.now(UTC)

        # Reconnection tracking
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_base_delay = 5  # seconds
        self.last_reconnect_attempt: Optional[datetime] = None

    async def record_bar_received(self) -> None:
        """Record that a bar was successfully received."""
        self.last_bar_timestamp = datetime.now(UTC)
        self.last_check = datetime.now(UTC)

        # Reset error count on successful bar
        if self.connection_errors > 0:
            logger.info(f"Connection restored after {self.connection_errors} errors")
            self.connection_errors = 0
            self.is_healthy = True

    async def record_order_submitted(self) -> None:
        """Record that an order was successfully submitted."""
        self.last_order_timestamp = datetime.now(UTC)
        self.last_check = datetime.now(UTC)

    async def record_connection_error(self, error_message: str) -> None:
        """Record a connection error.

        Args:
            error_message: Description of the error
        """
        self.connection_errors += 1
        self.last_check = datetime.now(UTC)
        logger.warning(
            f"Connection error #{self.connection_errors}: {error_message}"
        )

        # Mark unhealthy after threshold
        if self.connection_errors >= 3:
            self.is_healthy = False
            logger.error(f"Bot marked unhealthy after {self.connection_errors} errors")

    def should_attempt_reconnect(self) -> bool:
        """Check if reconnect should be attempted.

        Uses exponential backoff: 5s, 10s, 20s, 40s, 80s

        Returns:
            True if reconnect should be attempted, False otherwise.
        """
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(
                f"Max reconnect attempts ({self.max_reconnect_attempts}) reached. "
                "Manual intervention required."
            )
            return False

        if self.last_reconnect_attempt is None:
            return True

        # Calculate exponential backoff delay
        delay = self.reconnect_base_delay * (2 ** self.reconnect_attempts)
        elapsed = (datetime.now(UTC) - self.last_reconnect_attempt).total_seconds()

        return elapsed >= delay

    def get_reconnect_delay(self) -> int:
        """Get the delay before next reconnect attempt (in seconds).

        Returns:
            Delay in seconds (exponential backoff).
        """
        return self.reconnect_base_delay * (2 ** self.reconnect_attempts)

    async def record_reconnect_attempt(self, success: bool) -> None:
        """Record a reconnection attempt.

        Args:
            success: Whether the reconnect was successful.
        """
        self.last_reconnect_attempt = datetime.now(UTC)

        if success:
            self.reconnect_attempts = 0
            self.is_healthy = True
            logger.info("Reconnection successful")
        else:
            self.reconnect_attempts += 1
            logger.warning(f"Reconnection attempt #{self.reconnect_attempts} failed")

    def is_stale(self, stale_threshold_seconds: int = 300) -> bool:
        """Check if data is stale (no bars received recently).

        Args:
            stale_threshold_seconds: Threshold for stale data (default 5 minutes).

        Returns:
            True if no bars received within threshold, False otherwise.
        """
        if self.last_bar_timestamp is None:
            return True

        elapsed = (datetime.now(UTC) - self.last_bar_timestamp).total_seconds()
        is_stale = elapsed > stale_threshold_seconds

        if is_stale:
            logger.warning(
                f"Data is stale: {elapsed:.0f}s since last bar "
                f"(threshold: {stale_threshold_seconds}s)"
            )

        return is_stale

    async def save_health_check(self) -> None:
        """Save current health status to database."""
        try:
            async with self.session_factory() as session:
                health_check = HealthCheck(
                    broker=self.broker,
                    strategy=self.strategy,
                    bot_name=self.bot_name if self.bot_name else None,
                    is_healthy=self.is_healthy,
                    last_bar_timestamp=self.last_bar_timestamp,
                    last_order_timestamp=self.last_order_timestamp,
                    connection_errors=self.connection_errors,
                    checked_at=datetime.now(UTC),
                )
                session.add(health_check)
                await session.commit()

            logger.debug(
                f"Health check saved - is_healthy: {self.is_healthy}, "
                f"errors: {self.connection_errors}"
            )

        except Exception as e:
            logger.error(f"Failed to save health check: {e}")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get current health status.

        Returns:
            Dictionary with health status information.
        """
        return {
            'broker': self.broker,
            'strategy': self.strategy,
            'is_healthy': self.is_healthy,
            'connection_errors': self.connection_errors,
            'last_bar_timestamp': self.last_bar_timestamp,
            'last_order_timestamp': self.last_order_timestamp,
            'last_check': self.last_check,
            'reconnect_attempts': self.reconnect_attempts,
            'is_stale': self.is_stale(),
        }

    def __repr__(self) -> str:
        """String representation of health status."""
        status_str = "🟢 HEALTHY" if self.is_healthy else "🔴 UNHEALTHY"
        return (
            f"HealthCheck({status_str} | "
            f"errors: {self.connection_errors} | "
            f"reconnects: {self.reconnect_attempts}/{self.max_reconnect_attempts})"
        )


class HealthCheckRegistry:
    """Registry for managing multiple health checks (one per broker/strategy combo)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        """Initialize health check registry.

        Args:
            session_factory: Async sessionmaker factory
        """
        self.session_factory = session_factory
        self._checks: Dict[str, HealthCheckManager] = {}

    def register(
        self,
        broker: str,
        strategy: str,
        bot_name: Optional[str] = None,
    ) -> HealthCheckManager:
        """Register a health check for a broker/strategy combination.

        Args:
            broker: Broker name
            strategy: Strategy name
            bot_name: Optional bot instance name (for multi-bot tracking)

        Returns:
            HealthCheckManager instance
        """
        key = f"{bot_name or ''}:{broker}:{strategy}"
        if key not in self._checks:
            self._checks[key] = HealthCheckManager(
                self.session_factory, broker, strategy, bot_name
            )
            logger.info(f"Registered health check for {key}")

        return self._checks[key]

    def get(
        self,
        broker: str,
        strategy: str,
        bot_name: Optional[str] = None,
    ) -> Optional[HealthCheckManager]:
        """Get health check for a broker/strategy combination.

        Args:
            broker: Broker name
            strategy: Strategy name
            bot_name: Optional bot instance name (for multi-bot tracking)

        Returns:
            HealthCheckManager if registered, None otherwise.
        """
        key = f"{bot_name or ''}:{broker}:{strategy}"
        return self._checks.get(key)

    async def save_all(self) -> None:
        """Save all health checks to database."""
        for check in self._checks.values():
            await check.save_health_check()

    async def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered health checks.

        Returns:
            Dictionary mapping check keys to status dictionaries.
        """
        status = {}
        for key, check in self._checks.items():
            status[key] = await check.get_health_status()
        return status

    def get_unhealthy_checks(self) -> list:
        """Get all unhealthy checks.

        Returns:
            List of unhealthy HealthCheckManager instances.
        """
        return [check for check in self._checks.values() if not check.is_healthy]

    def get_stale_checks(self) -> list:
        """Get all checks with stale data.

        Returns:
            List of HealthCheckManager instances with stale data.
        """
        return [check for check in self._checks.values() if check.is_stale()]

    def log_all_status(self) -> None:
        """Log status of all health checks."""
        logger.info("=== Health Check Status ===")
        for key, check in self._checks.items():
            logger.info(f"{key}: {check}")

        unhealthy = self.get_unhealthy_checks()
        if unhealthy:
            logger.warning(f"⚠️  {len(unhealthy)} unhealthy checks detected")

        stale = self.get_stale_checks()
        if stale:
            logger.warning(f"⚠️  {len(stale)} checks with stale data")
