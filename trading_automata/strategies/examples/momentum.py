import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from collections import deque

from trading_automata.strategies.base import BaseStrategy, Signal
from trading_automata.data.models import Bar, Quote, Trade
from trading_automata.monitoring.event_logger import EventLogger


logger = logging.getLogger(__name__)


class MomentumStrategy(BaseStrategy):
    """Momentum strategy based on price changes.

    Generates buy signals when momentum (rate of price change) is high
    and sell signals when momentum is negative.
    """

    def __init__(self, name: str, config: Dict[str, Any], event_logger: Optional[EventLogger] = None):
        super().__init__(name, config, event_logger)
        self.lookback_period = config.get('lookback_period', 14)
        self.momentum_threshold = Decimal(str(config.get('momentum_threshold', 0.02)))
        self.position_size = Decimal(str(config.get('position_size', 100)))

        # Price history per symbol
        self.price_histories = {}

    def on_bar(self, bar: Bar) -> Optional[Signal]:
        """Generate signals based on momentum.

        Args:
            bar: Bar data

        Returns:
            Buy/sell signal or None.
        """
        self.record_bar()

        # Initialize price history for this symbol if needed
        if bar.symbol not in self.price_histories:
            self.price_histories[bar.symbol] = deque(maxlen=self.lookback_period + 1)

        # Add current close to history
        self.price_histories[bar.symbol].append(float(bar.close))

        # Need enough data for calculation
        if len(self.price_histories[bar.symbol]) < self.lookback_period + 1:
            return None

        prices = list(self.price_histories[bar.symbol])
        current_price = prices[-1]
        past_price = prices[0]

        # Calculate momentum (percentage change)
        momentum = (current_price - past_price) / past_price

        # Buy on positive momentum
        if momentum > float(self.momentum_threshold):
            signal = Signal(
                symbol=bar.symbol,
                action='buy',
                quantity=self.position_size,
                confidence=min(0.95, 0.5 + momentum),  # Higher confidence for stronger momentum
                metadata={
                    'strategy': 'momentum',
                    'price': bar.close,
                    'momentum': Decimal(str(momentum)),
                }
            )
            self.record_signal(signal)
            logger.info(f"BUY signal: {signal}")
            return signal

        # Sell on negative momentum
        elif momentum < -float(self.momentum_threshold):
            signal = Signal(
                symbol=bar.symbol,
                action='sell',
                quantity=self.position_size,
                confidence=min(0.95, 0.5 + abs(momentum)),
                metadata={
                    'strategy': 'momentum',
                    'price': bar.close,
                    'momentum': Decimal(str(momentum)),
                }
            )
            self.record_signal(signal)
            logger.info(f"SELL signal: {signal}")
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
            True if parameters are valid.
        """
        if self.lookback_period <= 0:
            logger.error(f"Invalid lookback_period: {self.lookback_period}")
            return False
        if self.momentum_threshold < 0:
            logger.error(f"Invalid momentum_threshold: {self.momentum_threshold}")
            return False
        if self.position_size <= 0:
            logger.error(f"Invalid position_size: {self.position_size}")
            return False
        return True
