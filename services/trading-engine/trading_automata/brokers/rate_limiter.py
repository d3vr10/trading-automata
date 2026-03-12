"""Rate limit handler with retry logic for broker API calls.

Wraps broker instances to automatically retry on 429/rate-limit errors
with exponential backoff. Works with any IBroker implementation.

Usage:
    broker = AlpacaBroker(api_key, secret_key, env)
    broker = RateLimitedBroker(broker, max_retries=3)
    broker.connect()  # transparent wrapper
"""

import functools
import logging
import time
from typing import Any

from trading_automata.metrics import engine_rate_limit_retries_total

logger = logging.getLogger(__name__)

# Known rate-limit error patterns across broker SDKs
_RATE_LIMIT_PATTERNS = (
    "429",
    "rate limit",
    "too many requests",
    "rate_limit_exceeded",
    "throttled",
)


def _is_rate_limit_error(exc: Exception) -> bool:
    """Check if an exception is a rate-limit error."""
    msg = str(exc).lower()
    return any(pattern in msg for pattern in _RATE_LIMIT_PATTERNS)


def retry_on_rate_limit(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator that retries a function on rate-limit errors.

    Uses exponential backoff with jitter. Non-rate-limit errors
    are raised immediately.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    if not _is_rate_limit_error(exc) or attempt >= max_retries:
                        raise
                    last_exc = exc
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"Rate limited (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {delay:.1f}s: {exc}"
                    )
                    time.sleep(delay)
            raise last_exc  # should not reach here
        return wrapper
    return decorator


class RateLimitedBroker:
    """Transparent wrapper that adds retry-on-429 to any IBroker.

    Proxies all method calls through the rate limit handler.
    Methods like connect/disconnect are passed through without retry.
    """

    # Methods that should NOT be retried (connection lifecycle)
    _NO_RETRY_METHODS = {"connect", "disconnect", "get_environment"}

    def __init__(self, broker, max_retries: int = 3, base_delay: float = 1.0, bot_name: str = ""):
        self._broker = broker
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._bot_name = bot_name

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._broker, name)

        if not callable(attr) or name.startswith("_") or name in self._NO_RETRY_METHODS:
            return attr

        @functools.wraps(attr)
        def wrapped(*args, **kwargs):
            last_exc = None
            for attempt in range(self._max_retries + 1):
                try:
                    return attr(*args, **kwargs)
                except Exception as exc:
                    if not _is_rate_limit_error(exc) or attempt >= self._max_retries:
                        raise
                    last_exc = exc
                    delay = self._base_delay * (2 ** attempt)
                    engine_rate_limit_retries_total.labels(
                        bot_name=self._bot_name, method=name,
                    ).inc()
                    logger.warning(
                        f"[{name}] Rate limited (attempt {attempt + 1}/{self._max_retries + 1}), "
                        f"retrying in {delay:.1f}s: {exc}"
                    )
                    time.sleep(delay)
            raise last_exc

        return wrapped
