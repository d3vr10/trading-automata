import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from collections import deque

from trading_automata.strategies.base import BaseStrategy, Signal
from trading_automata.data.models import Bar, Quote, Trade
from trading_automata.monitoring.event_logger import EventLogger


logger = logging.getLogger(__name__)


class MomentumStrategy(BaseStrategy):
    """Momentum strategy based on rate of price change.

    Enters long when momentum exceeds threshold, exits when momentum
    reverses below negative threshold.

    Position-aware: only one position per symbol at a time.
    """

    def __init__(self, name: str, config: Dict[str, Any], event_logger: Optional[EventLogger] = None):
        super().__init__(name, config, event_logger)
        self.lookback_period = config.get('lookback_period', 14)
        self.momentum_threshold = Decimal(str(config.get('momentum_threshold', 0.02)))
        self.position_size = Decimal(str(config.get('position_size', 100)))

        # Price history per symbol
        self.price_histories = {}

        # Position tracking: symbol -> 'long' or None
        self._position_state: Dict[str, Optional[str]] = {}

    def on_bar(self, bar: Bar) -> Optional[Signal]:
        self.record_bar()

        if bar.symbol not in self.price_histories:
            self.price_histories[bar.symbol] = deque(maxlen=self.lookback_period + 1)
            self._position_state[bar.symbol] = None

        self.price_histories[bar.symbol].append(float(bar.close))

        if len(self.price_histories[bar.symbol]) < self.lookback_period + 1:
            return None

        prices = list(self.price_histories[bar.symbol])
        current_price = prices[-1]
        past_price = prices[0]

        if past_price == 0:
            return None

        momentum = (current_price - past_price) / past_price
        in_position = self._position_state.get(bar.symbol) == 'long'

        # Entry: buy on strong positive momentum (only if not already in position)
        if not in_position and momentum > float(self.momentum_threshold):
            self._position_state[bar.symbol] = 'long'
            signal = Signal(
                symbol=bar.symbol,
                action='buy',
                quantity=self.position_size,
                confidence=min(0.95, 0.5 + momentum),
                metadata={
                    'strategy': 'momentum',
                    'price': bar.close,
                    'momentum': Decimal(str(round(momentum, 6))),
                }
            )
            self.record_signal(signal)
            return signal

        # Exit: sell on negative momentum reversal (only if in position)
        if in_position and momentum < -float(self.momentum_threshold):
            self._position_state[bar.symbol] = None
            signal = Signal(
                symbol=bar.symbol,
                action='sell',
                quantity=self.position_size,
                confidence=min(0.95, 0.5 + abs(momentum)),
                metadata={
                    'strategy': 'momentum',
                    'price': bar.close,
                    'momentum': Decimal(str(round(momentum, 6))),
                }
            )
            self.record_signal(signal)
            return signal

        return None

    def on_quote(self, quote: Quote) -> Optional[Signal]:
        return None

    def validate_config(self) -> bool:
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
