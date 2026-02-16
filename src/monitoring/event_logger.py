"""Event logging for trading decisions and strategy execution.

Logs trading events to both stdout (real-time) and database (historical analysis).
Tracks decision points: bars received, filters applied, signals generated, orders submitted.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
import psycopg


logger = logging.getLogger('trading_bot.events')


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

    def __init__(self, db_url: str = None):
        """Initialize event logger.

        Args:
            db_url: Database URL for storing events. If None, only logs to stdout.
        """
        self.db_url = db_url
        self.enabled = db_url is not None

    def log_bar_received(
        self,
        symbol: str,
        strategy: str,
        broker: str,
        details: Dict[str, Any],
    ):
        """Log when a new bar is received."""
        self._log(
            event_type=self.EVENT_BAR_RECEIVED,
            symbol=symbol,
            strategy=strategy,
            broker=broker,
            severity=self.SEV_DEBUG,
            message=f"Bar received for {symbol}",
            details=details,
        )
        logger.debug(f"[{symbol}] Bar received: O={details.get('open')}, H={details.get('high')}, L={details.get('low')}, C={details.get('close')}")

    def log_filter_check(
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

        self._log(
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

    def log_signal_generated(
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
        self._log(
            event_type=self.EVENT_SIGNAL_GENERATED,
            symbol=symbol,
            strategy=strategy,
            broker=broker,
            severity=self.SEV_INFO,
            message=f"Signal generated: {action.upper()} {quantity} @ confidence {confidence:.2f}",
            details=details,
        )
        logger.info(f"[{symbol}] 🎯 SIGNAL: {action.upper()} qty={quantity}, confidence={confidence:.2f}")

    def log_order_submitted(
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

        self._log(
            event_type=self.EVENT_ORDER_SUBMITTED,
            symbol=symbol,
            strategy=strategy,
            broker=broker,
            severity=self.SEV_INFO,
            message=f"Order submitted: {order_id}",
            details=details,
        )
        logger.info(f"[{symbol}] ✓ Order submitted: {order_id}, {side.upper()} {quantity}")

    def log_order_filled(
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

        self._log(
            event_type=self.EVENT_ORDER_FILLED,
            symbol=symbol,
            strategy=strategy,
            broker=broker,
            severity=self.SEV_INFO,
            message=f"Order filled: {order_id}",
            details=details,
        )
        logger.info(f"[{symbol}] ✓ Order FILLED: {order_id}, {side.upper()} {quantity} @ {filled_price:.2f}")

    def log_order_failed(
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

        self._log(
            event_type=self.EVENT_ORDER_FAILED,
            symbol=symbol,
            strategy=strategy,
            broker=broker,
            severity=self.SEV_ERROR,
            message=f"Order failed: {order_id} - {reason}",
            details=details,
        )
        logger.error(f"[{symbol}] ✗ Order FAILED: {order_id} - {reason}")

    def log_error(
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

        self._log(
            event_type=self.EVENT_ERROR,
            symbol=symbol,
            strategy=strategy,
            broker=broker,
            severity=self.SEV_ERROR,
            message=message,
            details=details,
        )
        logger.error(f"[{symbol}] ERROR: {message}")

    def log_warning(
        self,
        symbol: str,
        strategy: str,
        broker: str,
        message: str,
        details: Dict[str, Any] = None,
    ):
        """Log a warning event."""
        self._log(
            event_type=self.EVENT_WARNING,
            symbol=symbol,
            strategy=strategy,
            broker=broker,
            severity=self.SEV_WARNING,
            message=message,
            details=details or {},
        )
        logger.warning(f"[{symbol}] WARNING: {message}")

    def _log(
        self,
        event_type: str,
        symbol: str,
        strategy: str,
        broker: str,
        severity: str,
        message: str,
        details: Dict[str, Any],
    ):
        """Internal method to log to database."""
        if not self.enabled:
            return

        try:
            conn = psycopg.connect(self.db_url)
            try:
                conn.execute(
                    """
                    INSERT INTO trading_events
                    (event_type, event_timestamp, severity, strategy, symbol, broker, message, details)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event_type,
                        datetime.utcnow(),
                        severity,
                        strategy,
                        symbol,
                        broker,
                        message,
                        json.dumps(details) if details else None,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Failed to log event to database: {e}")


# Global event logger instance
_event_logger: Optional[EventLogger] = None


def init_event_logger(db_url: str = None) -> EventLogger:
    """Initialize the global event logger."""
    global _event_logger
    _event_logger = EventLogger(db_url)
    return _event_logger


def get_event_logger() -> EventLogger:
    """Get the global event logger instance."""
    global _event_logger
    if _event_logger is None:
        _event_logger = EventLogger()  # No database logging if not initialized
    return _event_logger
