"""SigmaSeriesAlphaStrategy - Conservative mean-reversion trading.

Conservative, high-probability entries for steady growth.

Strategy Overview:
- Uses trend filter (EMA 50/200) to identify macro trend
- Mean-reversion signals from Bollinger Bands
- RSI(14) for overbought/oversold conditions
- Stochastic(14,3,3) for momentum confirmation
- ATR(14) for dynamic risk sizing

Buy Signal (Mean-reversion in uptrend):
- Price > EMA(200) (in uptrend)
- Price < Lower Bollinger Band (oversold)
- RSI < 30 (extreme oversold)
- Stochastic %K crosses above %D (momentum turning)

Sell Signal (Mean-reversion in downtrend):
- Price < EMA(200) (in downtrend)
- Price > Upper Bollinger Band (overbought)
- RSI > 70 (extreme overbought)
- Stochastic %K crosses below %D (momentum turning)

Risk Management:
- Stop Loss: 1.5x ATR below entry (buy) or above entry (sell)
- Take Profit: 3.0x ATR above entry (buy) or below entry (sell)
- No time-based exit (hold until TP/SL)
- Signal cooldown: 5 bars
"""

from collections import deque
from decimal import Decimal
from typing import Optional, Dict, Any

from trading_bot.data.models import Bar
from trading_bot.strategies.base import BaseStrategy, Signal


class SigmaSeriesAlphaStrategy(BaseStrategy):
    """Conservative mean-reversion strategy targeting steady growth."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize SigmaSeriesAlphaStrategy.

        Args:
            config: Strategy configuration dict with symbols, etc.
        """
        super().__init__(config)
        self.name = "SigmaSeriesAlphaStrategy"

        # Indicator parameters
        self.rsi_period = 14
        self.ema_macro_fast = 50
        self.ema_macro_slow = 200
        self.bb_period = 20
        self.bb_std_dev = 2.0
        self.stoch_period = 14
        self.stoch_k_smooth = 3
        self.stoch_d_smooth = 3
        self.atr_period = 14

        # Risk parameters
        self.sl_atr_multiplier = 1.5
        self.tp_atr_multiplier = 3.0
        self.signal_cooldown_bars = 5

        # Data buffers
        self.bars_deque: Dict[str, deque] = {}
        self.last_signal_bar: Dict[str, int] = {}
        self.stoch_k_values: Dict[str, deque] = {}  # For smoothing %K and %D

        self.max_buffer_size = 100

    def on_bar(self, bar: Bar) -> Optional[Signal]:
        """Process a bar and generate trading signal.

        Args:
            bar: Bar data to process

        Returns:
            Trading signal or None if no signal
        """
        # Initialize buffers for this symbol
        if bar.symbol not in self.bars_deque:
            self.bars_deque[bar.symbol] = deque(maxlen=self.max_buffer_size)
            self.last_signal_bar[bar.symbol] = -self.signal_cooldown_bars - 1
            self.stoch_k_values[bar.symbol] = deque(maxlen=self.stoch_k_smooth + 5)

        buf = self.bars_deque[bar.symbol]
        buf.append(bar)

        # Need minimum bars for indicators
        if len(buf) < max(self.ema_macro_slow, self.bb_period, self.stoch_period):
            return None

        try:
            # Calculate indicators
            ema_fast = self._calc_ema(buf, self.ema_macro_fast)
            ema_slow = self._calc_ema(buf, self.ema_macro_slow)
            rsi = self._calc_rsi(buf, self.rsi_period)
            bb_upper, bb_lower = self._calc_bollinger_bands(buf, self.bb_period, self.bb_std_dev)
            stoch_k, stoch_d = self._calc_stochastic(buf, self.stoch_period, self.stoch_k_smooth, self.stoch_d_smooth)
            atr = self._calc_atr(buf, self.atr_period)

            current_bar_idx = len(buf) - 1
            last_signal_idx = self.last_signal_bar[bar.symbol]
            bars_since_signal = current_bar_idx - last_signal_idx

            # Check cooldown
            if bars_since_signal < self.signal_cooldown_bars:
                return None

            curr_close = Decimal(str(bar.close))
            prev_close = Decimal(str(buf[-2].close)) if len(buf) > 1 else curr_close

            # Get previous stochastic values for crossover
            prev_stoch_k = self.stoch_k_values[bar.symbol][-2] if len(self.stoch_k_values[bar.symbol]) >= 2 else stoch_k

            # BUY signal (mean-reversion in uptrend)
            if (
                ema_fast > ema_slow  # Uptrend
                and curr_close < Decimal(str(bb_lower))  # Below lower BB
                and rsi < 30  # Oversold
                and stoch_k > prev_stoch_k  # Stochastic crossing up
                and stoch_k < 50  # Not yet recovered
            ):
                sl_price = float(curr_close) - (float(atr) * self.sl_atr_multiplier)
                tp_price = float(curr_close) + (float(atr) * self.tp_atr_multiplier)

                self.last_signal_bar[bar.symbol] = current_bar_idx

                return Signal(
                    symbol=bar.symbol,
                    action="buy",
                    quantity=self._calculate_qty(bar),
                    confidence=0.80,
                    metadata={
                        "strategy": self.name,
                        "price": float(bar.close),
                        "stop_loss": sl_price,
                        "take_profit": tp_price,
                        "reason": "Mean-reversion in uptrend",
                        "atr": float(atr),
                        "rsi": float(rsi),
                        "stoch_k": float(stoch_k),
                        "bb_lower": float(bb_lower),
                    },
                )

            # SELL signal (mean-reversion in downtrend)
            if (
                ema_fast < ema_slow  # Downtrend
                and curr_close > Decimal(str(bb_upper))  # Above upper BB
                and rsi > 70  # Overbought
                and stoch_k < prev_stoch_k  # Stochastic crossing down
                and stoch_k > 50  # Not yet declined
            ):
                sl_price = float(curr_close) + (float(atr) * self.sl_atr_multiplier)
                tp_price = float(curr_close) - (float(atr) * self.tp_atr_multiplier)

                self.last_signal_bar[bar.symbol] = current_bar_idx

                return Signal(
                    symbol=bar.symbol,
                    action="sell",
                    quantity=self._calculate_qty(bar),
                    confidence=0.80,
                    metadata={
                        "strategy": self.name,
                        "price": float(bar.close),
                        "stop_loss": sl_price,
                        "take_profit": tp_price,
                        "reason": "Mean-reversion in downtrend",
                        "atr": float(atr),
                        "rsi": float(rsi),
                        "stoch_k": float(stoch_k),
                        "bb_upper": float(bb_upper),
                    },
                )

        except Exception as e:
            self.log(f"Error processing bar for {bar.symbol}: {e}")

        return None

    def _calc_ema(self, bars: deque, period: int) -> float:
        """Calculate EMA from bars."""
        if len(bars) < period:
            return float(bars[-1].close)

        multiplier = 2.0 / (period + 1)
        ema = float(bars[0].close)

        for bar in list(bars)[1:]:
            ema = float(bar.close) * multiplier + ema * (1 - multiplier)

        return ema

    def _calc_rsi(self, bars: deque, period: int) -> float:
        """Calculate RSI from bars."""
        if len(bars) < period + 1:
            return 50.0

        deltas = []
        for i in range(1, len(bars)):
            deltas.append(float(bars[i].close) - float(bars[i - 1].close))

        gains = [d for d in deltas[-period:] if d > 0]
        losses = [abs(d) for d in deltas[-period:] if d < 0]

        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calc_bollinger_bands(self, bars: deque, period: int, std_dev: float):
        """Calculate Bollinger Bands."""
        if len(bars) < period:
            close = float(bars[-1].close)
            return close, close

        closes = [float(bar.close) for bar in list(bars)[-period:]]
        sma = sum(closes) / period
        variance = sum((c - sma) ** 2 for c in closes) / period
        std = variance ** 0.5

        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)

        return upper, lower

    def _calc_stochastic(self, bars: deque, period: int, k_smooth: int, d_smooth: int):
        """Calculate Stochastic %K and %D."""
        if len(bars) < period:
            return 50.0, 50.0

        recent_bars = list(bars)[-period:]
        highest = max(b.high for b in recent_bars)
        lowest = min(b.low for b in recent_bars)

        current_close = float(bars[-1].close)
        range_val = highest - lowest

        if range_val == 0:
            raw_k = 50.0
        else:
            raw_k = 100 * (current_close - lowest) / range_val

        # Smooth %K
        self.stoch_k_values[bars[-1].symbol].append(raw_k)

        if len(self.stoch_k_values[bars[-1].symbol]) >= k_smooth:
            k = sum(list(self.stoch_k_values[bars[-1].symbol])[-k_smooth:]) / k_smooth
        else:
            k = raw_k

        # %D is SMA of %K
        if len(self.stoch_k_values[bars[-1].symbol]) >= k_smooth + d_smooth:
            d = sum(list(self.stoch_k_values[bars[-1].symbol])[-d_smooth:]) / d_smooth
        else:
            d = k

        return k, d

    def _calc_atr(self, bars: deque, period: int) -> float:
        """Calculate ATR from bars."""
        if len(bars) < period:
            return 0.0

        trs = []
        for i in range(1, len(bars)):
            bar = bars[i]
            prev_bar = bars[i - 1]

            tr = max(
                bar.high - bar.low,
                abs(bar.high - prev_bar.close),
                abs(bar.low - prev_bar.close),
            )
            trs.append(tr)

        atr = sum(trs[-period:]) / period if trs else 0
        return atr

    def _calculate_qty(self, bar: Bar) -> float:
        """Calculate position size based on price and risk."""
        # Simple fixed quantity for now
        return 1.0

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        return {
            "name": self.name,
            "symbols": self.config.get("symbols", []),
            "signals_generated": sum(1 for _ in self.last_signal_bar.values()),
        }
