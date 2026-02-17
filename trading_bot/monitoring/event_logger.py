"""Event logging for trading decisions and strategy execution.

Logs trading events to both stdout (real-time) and database (historical analysis).
Tracks decision points: bars received, filters applied, signals generated, orders submitted.
"""

import json
import logging
from datetime import datetime, UTC
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trading_bot.database.models import TradingEvent

logger = logging.getLogger('trading_bot.events')


class DecimalJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal objects."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class EventLogger:
    """Logs trading events to database and stdout for troubleshooting."""

    # Event types
    EVENT_BAR_RECEIVED = "BAR_RECEIVED"
    EVENT_FILTER_CHECKED = "FILTER_CHECKED"
    EVENT_FILTER_PASSED = "FILTER_PASSED"
    EVENT_FILTER_FAILED = "FILTER_FAILED"
    EVENT_SIGNAL_GENERATED = "SIGNAL_GENERATED"
    EVENT_ORDER_SUBMITTED = "ORDER_SUBMITTED"
    EVENT_ORDER_FILLED = "ORDER_FILLED"
    EVENT_ORDER_FAILED = "ORDER_FAILED"
    EVENT_ERROR = "ERROR"
    EVENT_WARNING = "WARNING"
    EVENT_INFO = "INFO"

    # Severity levels
    SEV_DEBUG = "DEBUG"
    SEV_INFO = "INFO"
    SEV_WARNING = "WARNING"
    SEV_ERROR = "ERROR"
    SEV_CRITICAL = "CRITICAL"

    def __init__(self, session_factory: Optional[async_sessionmaker[AsyncSession]] = None):
        """Initialize event logger.

        Args:
            session_factory: Async sessionmaker factory for storing events. If None, only logs to stdout.
        """
        self.session_factory = session_factory
        self.enabled = session_factory is not None

    async def log_bar_received(
        self,
        symbol: str,
        strategy: str,
        broker: str,
        details: Dict[str, Any],
    ):
        """Log when a new bar is received."""
        await self._log(
            event_type=self.EVENT_BAR_RECEIVED,
            symbol=symbol,
            strategy=strategy,
            broker=broker,
            severity=self.SEV_DEBUG,
            message=f"Bar received for {symbol}",
            details=details,
        )
        logger.debug(f"[{symbol}] Bar received: O={details.get('open')}, H={details.get('high')}, L={details.get('low')}, C={details.get('close')}")

    async def log_filter_check(
        self,
        symbol: str,
        strategy: str,
        broker: str,
        filter_name: str,
        passed: bool,
        message: str,
        details: Dict[str, Any],
    ):
        """Log filter check results."""
        event_type = self.EVENT_FILTER_PASSED if passed else self.EVENT_FILTER_FAILED
        severity = self.SEV_DEBUG if passed else self.SEV_WARNING
        status = "✓ PASS" if passed else "✗ FAIL"

        await self._log(
            event_type=event_type,
            symbol=symbol,
            strategy=strategy,
            broker=broker,
            severity=severity,
            message=f"{status} {filter_name}: {message}",
            details=details,
        )

        log_fn = logger.debug if passed else logger.warning
        log_fn(f"[{symbol}] {status} {filter_name}: {message}")

    async def log_signal_generated(
        self,
        symbol: str,
        strategy: str,
        broker: str,
        action: str,
        quantity: float,
        confidence: float,
        details: Dict[str, Any],
    ):
        """Log when a trading signal is generated."""
        await self._log(
            event_type=self.EVENT_SIGNAL_GENERATED,
            symbol=symbol,
            strategy=strategy,
            broker=broker,
            severity=self.SEV_INFO,
            message=f"Signal generated: {action.upper()} {quantity} @ confidence {confidence:.2f}",
            details=details,
        )
        logger.info(f"[{symbol}] [{strategy}] 🎯 SIGNAL: {action.upper()} qty={quantity}, confidence={confidence:.2f}")

    async def log_order_submitted(
        self,
        symbol: str,
        strategy: str,
        broker: str,
        order_id: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        details: Dict[str, Any] = None,
    ):
        """Log when an order is submitted."""
        details = details or {}
        details.update({
            "order_id": order_id,
            "side": side,
            "quantity": quantity,
            "price": price,
        })

        await self._log(
            event_type=self.EVENT_ORDER_SUBMITTED,
            symbol=symbol,
            strategy=strategy,
            broker=broker,
            severity=self.SEV_INFO,
            message=f"Order submitted: {order_id}",
            details=details,
        )
        logger.info(f"[{symbol}] [{strategy}] ✓ Order submitted: {order_id}, {side.upper()} {quantity}")

    async def log_order_filled(
        self,
        symbol: str,
        strategy: str,
        broker: str,
        order_id: str,
        side: str,
        quantity: float,
        filled_price: float,
        details: Dict[str, Any] = None,
    ):
        """Log when an order is filled."""
        details = details or {}
        details.update({
            "order_id": order_id,
            "side": side,
            "quantity": quantity,
            "filled_price": filled_price,
        })

        await self._log(
            event_type=self.EVENT_ORDER_FILLED,
            symbol=symbol,
            strategy=strategy,
            broker=broker,
            severity=self.SEV_INFO,
            message=f"Order filled: {order_id}",
            details=details,
        )
        logger.info(f"[{symbol}] [{strategy}] ✓ Order FILLED: {order_id}, {side.upper()} {quantity} @ {filled_price:.2f}")

    async def log_order_failed(
        self,
        symbol: str,
        strategy: str,
        broker: str,
        order_id: str,
        reason: str,
        details: Dict[str, Any] = None,
    ):
        """Log when an order fails."""
        details = details or {}
        details["reason"] = reason

        await self._log(
            event_type=self.EVENT_ORDER_FAILED,
            symbol=symbol,
            strategy=strategy,
            broker=broker,
            severity=self.SEV_ERROR,
            message=f"Order failed: {order_id} - {reason}",
            details=details,
        )
        logger.error(f"[{symbol}] [{strategy}] ✗ Order FAILED: {order_id} - {reason}")

    async def log_error(
        self,
        symbol: str,
        strategy: str,
        broker: str,
        message: str,
        details: Dict[str, Any] = None,
        exception: Exception = None,
    ):
        """Log an error event."""
        details = details or {}
        if exception:
            details["exception"] = str(exception)
            details["exception_type"] = type(exception).__name__

        await self._log(
            event_type=self.EVENT_ERROR,
            symbol=symbol,
            strategy=strategy,
            broker=broker,
            severity=self.SEV_ERROR,
            message=message,
            details=details,
        )
        logger.error(f"[{symbol}] [{strategy}] ERROR: {message}")

    async def log_warning(
        self,
        symbol: str,
        strategy: str,
        broker: str,
        message: str,
        details: Dict[str, Any] = None,
    ):
        """Log a warning event."""
        await self._log(
            event_type=self.EVENT_WARNING,
            symbol=symbol,
            strategy=strategy,
            broker=broker,
            severity=self.SEV_WARNING,
            message=message,
            details=details or {},
        )
        logger.warning(f"[{symbol}] [{strategy}] WARNING: {message}")

    async def _log(
        self,
        event_type: str,
        symbol: str,
        strategy: str,
        broker: str,
        severity: str,
        message: str,
        details: Dict[str, Any],
    ):
        """Internal method to log to database using ORM."""
        if not self.enabled:
            return

        try:
            async with self.session_factory() as session:
                event = TradingEvent(
                    event_type=event_type,
                    event_timestamp=datetime.now(UTC),
                    severity=severity,
                    strategy=strategy,
                    symbol=symbol,
                    broker=broker,
                    message=message,
                    details=json.dumps(details, cls=DecimalJSONEncoder) if details else None,
                )
                session.add(event)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to log event to database: {e}")


# Global event logger instance
_event_logger: Optional[EventLogger] = None


def init_event_logger(session_factory: Optional[async_sessionmaker[AsyncSession]] = None) -> EventLogger:
    """Initialize the global event logger with async session factory."""
    global _event_logger
    _event_logger = EventLogger(session_factory)
    return _event_logger


def get_event_logger() -> EventLogger:
    """Get the global event logger instance."""
    global _event_logger
    if _event_logger is None:
        _event_logger = EventLogger()  # No database logging if not initialized
    return _event_logger
