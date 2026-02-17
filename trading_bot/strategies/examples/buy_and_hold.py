import logging
from typing import Dict, Any, Optional
from decimal import Decimal

from trading_bot.strategies.base import BaseStrategy, Signal
from trading_bot.data.models import Bar, Quote, Trade
from trading_bot.monitoring.event_logger import EventLogger


logger = logging.getLogger(__name__)


class BuyAndHoldStrategy(BaseStrategy):
    """Simple buy and hold strategy.

    Buys a fixed quantity of each symbol on the first bar,
    then holds forever.
    """

    def __init__(self, name: str, config: Dict[str, Any], event_logger: Optional[EventLogger] = None):
        super().__init__(name, config, event_logger)
        self.target_quantity = Decimal(str(config.get('quantity', 100)))
        self.bought = {}  # Track which symbols have been bought

    def on_bar(self, bar: Bar) -> Optional[Signal]:
        """Generate buy signal on first bar.

        Args:
            bar: Bar data

        Returns:
            Buy signal on first bar, None on subsequent bars.
        """
        self.record_bar()

        if bar.symbol not in self.bought:
            self.bought[bar.symbol] = True
            signal = Signal(
                symbol=bar.symbol,
                action='buy',
                quantity=self.target_quantity,
                confidence=1.0,
                metadata={
                    'strategy': 'buy_and_hold',
                    'price': bar.close,
                }
            )
            self.record_signal(signal)
            logger.info(f"BUY signal: {signal}")
            return signal

        return None

    def on_quote(self, quote: Quote) -> Optional[Signal]:
        """No quote-based signals.

        Args:
            quote: Quote data

        Returns:
            None
        """
        return None

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True if quantity is positive.
        """
        if self.target_quantity <= 0:
            logger.error(f"Invalid quantity: {self.target_quantity}")
            return False
        return True
