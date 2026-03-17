import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from collections import deque
import pandas as pd
import pandas_ta as ta

from trading_automata.strategies.base import BaseStrategy, Signal
from trading_automata.data.models import Bar, Quote
from trading_automata.monitoring.event_logger import EventLogger


logger = logging.getLogger(__name__)


class RSIATRTrendStrategy(BaseStrategy):
    """RSI + ATR + EMA Trend Following Strategy.

    A generic, asset-agnostic strategy that works for any tradable pair:
    - Stocks (SPY, QQQ, etc.)
    - Forex (EUR/USD, GBP/USD, etc.)
    - Crypto (BTC/USD, ETH/USD, etc.)
    - Commodities (Gold, Oil, etc.)

    Indicators used:
    - RSI (Relative Strength Index) for overbought/oversold signals
    - ATR (Average True Range) for volatility-based position sizing
    - EMA (Exponential Moving Averages) for trend confirmation
    - Support/Resistance levels
    - Risk-reward ratio enforcement

    Suitable for H1 (1-hour), H4 (4-hour), or daily timeframes.
    """

    def __init__(self, name: str, config: Dict[str, Any], event_logger: Optional[EventLogger] = None):
        super().__init__(name, config, event_logger)

        # RSI Configuration
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_oversold = config.get('rsi_oversold', 30)
        self.rsi_overbought = config.get('rsi_overbought', 70)

        # ATR Configuration
        self.atr_period = config.get('atr_period', 14)
        self.atr_multiplier = config.get('atr_multiplier', 1.5)

        # Moving Average Configuration
        self.ema_fast_period = config.get('ema_fast_period', 9)
        self.ema_slow_period = config.get('ema_slow_period', 21)

        # Risk Management
        self.position_size = Decimal(str(config.get('position_size', 10)))
        self.risk_reward_ratio = config.get('risk_reward_ratio', 2.0)
        self.max_daily_loss_pips = config.get('max_daily_loss_pips', 100)

        # Trading Control
        self.signal_cooldown = config.get('signal_cooldown_bars', 3)

        # ===== FILTERS (Volatility & Liquidity) =====
        # Liquidity Filter: Minimum volume (in units traded)
        self.min_volume = self.filters.get('min_volume', 100_000)

        # Volatility Filters (using ATR)
        self.min_atr = self.filters.get('min_atr', 0)  # Minimum volatility to trade
        self.max_atr = self.filters.get('max_atr', float('inf'))  # Maximum volatility to trade

        # Data storage for indicators
        self.price_history = {}
        self.high_history = {}
        self.low_history = {}
        self.volume_history = {}

        # Per-symbol tracking
        self.last_signal_time = {}
        self._signal_bar_count: Dict[str, int] = {}  # bars since last signal
        self._position_state: Dict[str, Optional[str]] = {}  # 'long' or None

        logger.debug(
            f"Strategy {name} initialized with filters: "
            f"min_volume={self.min_volume}, min_atr={self.min_atr}, max_atr={self.max_atr}"
        )

    def on_bar(self, bar: Bar) -> Optional[Signal]:
        """Process bar data and generate trading signals.

        Args:
            bar: OHLCV bar data

        Returns:
            Trading signal or None.
        """
        self.record_bar()

        # Initialize history for this symbol if needed
        if bar.symbol not in self.price_history:
            self._init_symbol_history(bar.symbol)

        # Add bar data to history
        self.price_history[bar.symbol].append(float(bar.close))
        self.high_history[bar.symbol].append(float(bar.high))
        self.low_history[bar.symbol].append(float(bar.low))
        self.volume_history[bar.symbol].append(float(bar.volume))

        # Need enough data for indicators
        min_required = max(self.rsi_period, self.ema_slow_period, self.atr_period) + 5
        if len(self.price_history[bar.symbol]) < min_required:
            logger.debug(
                f"Insufficient data for {bar.symbol}: "
                f"{len(self.price_history[bar.symbol])}/{min_required}"
            )
            return None

        # Check cooldown to prevent over-trading
        if not self._check_signal_cooldown(bar.symbol):
            return None

        # Apply filters (volume, volatility)
        if not self.should_trade(bar):
            logger.debug(
                f"Bar {bar.symbol} filtered out: "
                f"volume={bar.volume} (min: {self.min_volume})"
            )
            return None

        # Calculate indicators
        indicators = self._calculate_indicators(bar.symbol)
        if not indicators:
            return None

        # Generate signal based on indicators
        signal = self._generate_signal(bar, indicators)

        if signal:
            self.last_signal_time[bar.symbol] = bar.timestamp
            self._signal_bar_count[bar.symbol] = 0  # Reset cooldown
            if signal.action == 'buy':
                self._position_state[bar.symbol] = 'long'
            elif signal.action == 'sell':
                self._position_state[bar.symbol] = None
            self.record_signal(signal)
            logger.info(
                f"RSIATRTrend signal for {bar.symbol}: {signal} "
                f"(RSI={indicators['rsi']:.1f}, "
                f"ATR={indicators['atr']:.6f}, "
                f"Trend={'UP' if indicators['trend'] else 'DOWN'})"
            )

        return signal

    def on_quote(self, quote: Quote) -> Optional[Signal]:
        """No quote-based signals for this strategy.

        Args:
            quote: Quote data

        Returns:
            None
        """
        return None

    def validate_config(self) -> bool:
        """Validate strategy configuration.

        Returns:
            True if configuration is valid.
        """
        errors = []

        if self.rsi_period <= 0:
            errors.append(f"Invalid rsi_period: {self.rsi_period}")
        if self.rsi_oversold <= 0 or self.rsi_oversold >= self.rsi_overbought:
            errors.append(f"Invalid RSI levels: oversold={self.rsi_oversold}, overbought={self.rsi_overbought}")
        if self.atr_period <= 0:
            errors.append(f"Invalid atr_period: {self.atr_period}")
        if self.ema_fast_period <= 0 or self.ema_slow_period <= 0:
            errors.append(f"Invalid EMA periods: fast={self.ema_fast_period}, slow={self.ema_slow_period}")
        if self.ema_fast_period >= self.ema_slow_period:
            errors.append(f"EMA fast period ({self.ema_fast_period}) must be < slow period ({self.ema_slow_period})")
        if self.position_size <= 0:
            errors.append(f"Invalid position_size: {self.position_size}")
        if self.risk_reward_ratio <= 0:
            errors.append(f"Invalid risk_reward_ratio: {self.risk_reward_ratio}")

        if errors:
            for error in errors:
                logger.error(error)
            return False

        return True

    def _init_symbol_history(self, symbol: str) -> None:
        """Initialize history deques for a symbol.

        Args:
            symbol: Trading symbol
        """
        max_len = max(self.rsi_period, self.ema_slow_period, self.atr_period) + 50
        self.price_history[symbol] = deque(maxlen=max_len)
        self.high_history[symbol] = deque(maxlen=max_len)
        self.low_history[symbol] = deque(maxlen=max_len)
        self.volume_history[symbol] = deque(maxlen=max_len)

    def _check_signal_cooldown(self, symbol: str) -> bool:
        """Check if enough bars have passed since last signal.

        Args:
            symbol: Trading symbol

        Returns:
            True if cooldown has elapsed, False otherwise.
        """
        if symbol not in self._signal_bar_count:
            self._signal_bar_count[symbol] = self.signal_cooldown  # Allow first signal
            return True

        self._signal_bar_count[symbol] += 1
        return self._signal_bar_count[symbol] >= self.signal_cooldown

    def _check_volatility_filter(self, bar: Bar) -> bool:
        """Check volatility-based filters using ATR.

        Called by BaseStrategy.should_trade() to filter volatile/calm markets.

        Args:
            bar: Bar data to check

        Returns:
            True if volatility is acceptable, False if filtered out.
        """
        # Need sufficient history to calculate ATR
        if bar.symbol not in self.low_history:
            return True  # Allow first bars

        prices = list(self.price_history[bar.symbol])
        if len(prices) < self.atr_period:
            return True  # Allow if not enough data

        # Calculate current ATR
        atr = self._calculate_atr(
            list(self.high_history[bar.symbol]),
            list(self.low_history[bar.symbol]),
            prices
        )

        # Check volatility bounds
        if atr < self.min_atr:
            logger.debug(f"{bar.symbol}: ATR {atr:.2f} below min {self.min_atr:.2f} - too calm")
            return False  # Too calm, not enough movement

        if atr > self.max_atr:
            logger.debug(f"{bar.symbol}: ATR {atr:.2f} above max {self.max_atr:.2f} - too volatile")
            return False  # Too volatile, too risky

        return True

    def _calculate_indicators(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Calculate technical indicators for the symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Dictionary with indicator values or None if calculation fails.
        """
        try:
            prices = list(self.price_history[symbol])
            highs = list(self.high_history[symbol])
            lows = list(self.low_history[symbol])

            if len(prices) < self.rsi_period:
                return None

            # Calculate RSI
            rsi = self._calculate_rsi(prices)

            # Calculate ATR
            atr = self._calculate_atr(highs, lows, prices)

            # Calculate EMAs
            ema_fast = self._calculate_ema(prices, self.ema_fast_period)
            ema_slow = self._calculate_ema(prices, self.ema_slow_period)

            # Determine trend
            current_price = prices[-1]
            trend = current_price > ema_fast > ema_slow  # Bullish if price > fast EMA > slow EMA

            # Calculate support and resistance
            support, resistance = self._calculate_support_resistance(prices, highs, lows)

            return {
                'rsi': rsi,
                'atr': atr,
                'ema_fast': ema_fast,
                'ema_slow': ema_slow,
                'current_price': current_price,
                'trend': trend,
                'support': support,
                'resistance': resistance,
            }

        except Exception as e:
            logger.error(f"Failed to calculate indicators for {symbol}: {e}")
            return None

    def _calculate_rsi(self, prices: list, period: int = None) -> float:
        """Calculate RSI (Relative Strength Index).

        Args:
            prices: List of prices
            period: RSI period

        Returns:
            RSI value (0-100).
        """
        if period is None:
            period = self.rsi_period

        if len(prices) < period + 1:
            return 50.0  # Neutral

        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]

        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)

    def _calculate_ema(self, prices: list, period: int) -> float:
        """Calculate EMA (Exponential Moving Average).

        Args:
            prices: List of prices
            period: EMA period

        Returns:
            EMA value.
        """
        if len(prices) < period:
            return prices[-1]

        # Simple calculation for last EMA
        multiplier = 2.0 / (period + 1)
        ema = sum(prices[:period]) / period

        for price in prices[period:]:
            ema = price * multiplier + ema * (1 - multiplier)

        return float(ema)

    def _calculate_atr(self, highs: list, lows: list, closes: list, period: int = None) -> float:
        """Calculate ATR (Average True Range).

        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of close prices
            period: ATR period

        Returns:
            ATR value.
        """
        if period is None:
            period = self.atr_period

        if len(highs) < period + 1:
            return 0.0

        true_ranges = []
        for i in range(1, len(highs)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            true_ranges.append(tr)

        atr = sum(true_ranges[-period:]) / period if true_ranges else 0
        return float(atr)

    def _calculate_support_resistance(self, prices: list, highs: list, lows: list) -> tuple:
        """Calculate support and resistance levels.

        Args:
            prices: List of prices
            highs: List of high prices
            lows: List of low prices

        Returns:
            Tuple of (support, resistance).
        """
        lookback = min(20, len(prices))
        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]

        resistance = max(recent_highs)
        support = min(recent_lows)

        return float(support), float(resistance)

    def _generate_signal(self, bar: Bar, indicators: Dict[str, Any]) -> Optional[Signal]:
        """Generate trading signal based on indicators.

        Args:
            bar: Current bar data
            indicators: Calculated indicators

        Returns:
            Trading signal or None.
        """
        rsi = indicators['rsi']
        current_price = indicators['current_price']
        trend = indicators['trend']
        atr = indicators['atr']
        support = indicators['support']
        resistance = indicators['resistance']

        in_position = self._position_state.get(bar.symbol) == 'long'

        # Buy Signal: RSI oversold + Bullish trend (only if not in position)
        if not in_position and rsi < self.rsi_oversold and trend:
            return Signal(
                symbol=bar.symbol,
                action='buy',
                quantity=self.position_size,
                confidence=min(0.95, 0.6 + (30 - rsi) / 100),  # Higher confidence for deeper oversold
                metadata={
                    'strategy': 'eur_usd',
                    'price': bar.close,
                    'rsi': Decimal(str(rsi)),
                    'atr': Decimal(str(atr)),
                    'stop_loss': Decimal(str(support)),
                    'take_profit': Decimal(str(current_price + (current_price - support) * self.risk_reward_ratio)),
                    'trend': 'bullish',
                }
            )

        # Sell Signal: RSI overbought + Bearish trend (only if in position)
        elif in_position and rsi > self.rsi_overbought and not trend:
            return Signal(
                symbol=bar.symbol,
                action='sell',
                quantity=self.position_size,
                confidence=min(0.95, 0.6 + (rsi - 70) / 100),  # Higher confidence for deeper overbought
                metadata={
                    'strategy': 'eur_usd',
                    'price': bar.close,
                    'rsi': Decimal(str(rsi)),
                    'atr': Decimal(str(atr)),
                    'stop_loss': Decimal(str(resistance)),
                    'take_profit': Decimal(str(current_price - (resistance - current_price) * self.risk_reward_ratio)),
                    'trend': 'bearish',
                }
            )

        return None
