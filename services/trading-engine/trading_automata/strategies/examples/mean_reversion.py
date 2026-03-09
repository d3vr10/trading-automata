import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from collections import deque
import statistics

from trading_automata.strategies.base import BaseStrategy, Signal
from trading_automata.data.models import Bar, Quote, Trade
from trading_automata.monitoring.event_logger import EventLogger


logger = logging.getLogger(__name__)


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy using Bollinger Bands.

    Buys when price falls below the lower Bollinger Band (oversold),
    sells to exit when price reverts to or above the upper band.

    Position-aware: only one position per symbol at a time.
    """

    def __init__(self, name: str, config: Dict[str, Any], event_logger: Optional[EventLogger] = None):
        super().__init__(name, config, event_logger)
        self.window = config.get('window', 20)
        self.num_std = config.get('num_std', 2)
        self.position_size = Decimal(str(config.get('position_size', 100)))

        # Price history per symbol
        self.price_histories = {}

        # Position tracking: symbol -> 'long' or None
        self._position_state: Dict[str, Optional[str]] = {}

    def on_bar(self, bar: Bar) -> Optional[Signal]:
        self.record_bar()

        if bar.symbol not in self.price_histories:
            self.price_histories[bar.symbol] = deque(maxlen=self.window)
            self._position_state[bar.symbol] = None

        self.price_histories[bar.symbol].append(float(bar.close))

        if len(self.price_histories[bar.symbol]) < self.window:
            return None

        prices = list(self.price_histories[bar.symbol])
        mean = statistics.mean(prices)
        std = statistics.stdev(prices)

        if std == 0:
            return None

        upper_band = mean + (self.num_std * std)
        lower_band = mean - (self.num_std * std)
        current_price = float(bar.close)

        in_position = self._position_state.get(bar.symbol) == 'long'

        # Entry: buy when price touches lower band (only if not already in position)
        if not in_position and current_price <= lower_band:
            self._position_state[bar.symbol] = 'long'
            signal = Signal(
                symbol=bar.symbol,
                action='buy',
                quantity=self.position_size,
                confidence=0.8,
                metadata={
                    'strategy': 'mean_reversion',
                    'price': bar.close,
                    'lower_band': Decimal(str(round(lower_band, 6))),
                    'mean': Decimal(str(round(mean, 6))),
                }
            )
            self.record_signal(signal)
            return signal

        # Exit: sell when price reaches upper band (only if in position)
        if in_position and current_price >= upper_band:
            self._position_state[bar.symbol] = None
            signal = Signal(
                symbol=bar.symbol,
                action='sell',
                quantity=self.position_size,
                confidence=0.8,
                metadata={
                    'strategy': 'mean_reversion',
                    'price': bar.close,
                    'upper_band': Decimal(str(round(upper_band, 6))),
                    'mean': Decimal(str(round(mean, 6))),
                }
            )
            self.record_signal(signal)
            return signal

        return None

    def on_quote(self, quote: Quote) -> Optional[Signal]:
        return None

    def validate_config(self) -> bool:
        if self.window <= 0:
            logger.error(f"Invalid window: {self.window}")
            return False
        if self.num_std <= 0:
            logger.error(f"Invalid num_std: {self.num_std}")
            return False
        if self.position_size <= 0:
            logger.error(f"Invalid position_size: {self.position_size}")
            return False
        return True
