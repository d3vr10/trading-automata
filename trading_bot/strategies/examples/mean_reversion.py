import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from collections import deque
import statistics

from trading_bot.strategies.base import BaseStrategy, Signal
from trading_bot.data.models import Bar, Quote, Trade
from trading_bot.monitoring.event_logger import EventLogger


logger = logging.getLogger(__name__)


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy using Bollinger Bands.

    Generates buy signals when price falls below lower Bollinger Band
    and sell signals when price rises above upper Bollinger Band.
    """

    def __init__(self, name: str, config: Dict[str, Any], event_logger: Optional[EventLogger] = None):
        super().__init__(name, config, event_logger)
        self.window = config.get('window', 20)
        self.num_std = config.get('num_std', 2)
        self.position_size = Decimal(str(config.get('position_size', 100)))

        # Price history per symbol
        self.price_histories = {}

    def on_bar(self, bar: Bar) -> Optional[Signal]:
        """Generate signals based on Bollinger Bands.

        Args:
            bar: Bar data

        Returns:
            Buy/sell signal or None.
        """
        self.record_bar()

        # Initialize price history for this symbol if needed
        if bar.symbol not in self.price_histories:
            self.price_histories[bar.symbol] = deque(maxlen=self.window)

        # Add current close to history
        self.price_histories[bar.symbol].append(float(bar.close))

        # Need enough data for calculation
        if len(self.price_histories[bar.symbol]) < self.window:
            return None

        # Calculate Bollinger Bands
        prices = list(self.price_histories[bar.symbol])
        mean = statistics.mean(prices)
        std = statistics.stdev(prices)

        upper_band = mean + (self.num_std * std)
        lower_band = mean - (self.num_std * std)

        current_price = float(bar.close)

        # Buy when price touches lower band
        if current_price <= lower_band:
            signal = Signal(
                symbol=bar.symbol,
                action='buy',
                quantity=self.position_size,
                confidence=0.8,
                metadata={
                    'strategy': 'mean_reversion',
                    'price': bar.close,
                    'lower_band': Decimal(str(lower_band)),
                    'mean': Decimal(str(mean)),
                }
            )
            self.record_signal(signal)
            logger.info(f"BUY signal: {signal}")
            return signal

        # Sell when price touches upper band
        elif current_price >= upper_band:
            signal = Signal(
                symbol=bar.symbol,
                action='sell',
                quantity=self.position_size,
                confidence=0.8,
                metadata={
                    'strategy': 'mean_reversion',
                    'price': bar.close,
                    'upper_band': Decimal(str(upper_band)),
                    'mean': Decimal(str(mean)),
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
            True if window and num_std are valid.
        """
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
