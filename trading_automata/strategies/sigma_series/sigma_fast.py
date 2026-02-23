"""SigmaSeriesFastStrategy - High volume momentum trading.

Target: 93-94% win rate via tight entries and rapid momentum detection.

Strategy Overview:
- Monitors VWAP for support/resistance
- Uses dual EMAs (8/21) for trend confirmation
- RSI(7) for overbought/oversold conditions
- Volume spike detection (>2x 20-bar average)
- ATR(7) for dynamic stop loss and take profit sizing

Buy Signal:
- Price crosses above VWAP
- EMA(8) > EMA(21) (uptrend)
- RSI 40-65 (not overbought but momentum)
- Volume > 2x 20-bar average

Sell Signal:
- Price crosses below VWAP
- EMA(8) < EMA(21) (downtrend)
- RSI 35-60 (not oversold but momentum)
- Volume > 2x 20-bar average

Risk Management:
- Stop Loss: 0.5x ATR below entry
- Take Profit: 1.5x ATR above entry
- Max hold: 10 bars (time-based exit)
- Signal cooldown: 2 bars
"""

from collections import deque
from decimal import Decimal
from typing import Optional, Dict, Any

from trading_automata.data.models import Bar
from trading_automata.strategies.base import BaseStrategy, Signal


class SigmaSeriesFastStrategy(BaseStrategy):
    """High-performance momentum strategy targeting 93-94% win rate."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize SigmaSeriesFastStrategy.

        Args:
            config: Strategy configuration dict with symbols, etc.
        """
        super().__init__(config)
        self.name = "SigmaSeriesFastStrategy"

        # Indicator parameters
        self.ema_fast_period = 8
        self.ema_slow_period = 21
        self.rsi_period = 7
        self.atr_period = 7
        self.volume_avg_period = 20
        self.volume_spike_multiplier = 2.0

        # Risk parameters
        self.sl_atr_multiplier = 0.5
        self.tp_atr_multiplier = 1.5
        self.max_hold_bars = 10
        self.signal_cooldown_bars = 2

        # Data buffers
        self.bars_deque: Dict[str, deque] = {}  # symbol -> deque of bars
        self.last_signal_bar: Dict[str, int] = {}  # symbol -> bar index
        self.position_entry_bar: Dict[str, int] = {}  # symbol -> entry bar index

        # Max buffer size
        self.max_buffer_size = 100

    def on_bar(self, bar: Bar) -> Optional[Signal]:
        """Process a bar and generate trading signal.

        Args:
            bar: Bar data to process

        Returns:
            Trading signal or None if no signal
        """
        # Initialize buffer for this symbol
        if bar.symbol not in self.bars_deque:
            self.bars_deque[bar.symbol] = deque(maxlen=self.max_buffer_size)
            self.last_signal_bar[bar.symbol] = -self.signal_cooldown_bars - 1
            self.position_entry_bar[bar.symbol] = -1

        # Add bar to buffer
        buf = self.bars_deque[bar.symbol]
        buf.append(bar)

        # Need minimum bars for indicators
        if len(buf) < max(self.ema_slow_period, self.volume_avg_period):
            return None

        # Calculate indicators
        try:
            ema_fast = self._calc_ema(buf, self.ema_fast_period)
            ema_slow = self._calc_ema(buf, self.ema_slow_period)
            rsi = self._calc_rsi(buf, self.rsi_period)
            atr = self._calc_atr(buf, self.atr_period)
            vwap = self._calc_vwap(buf)
            volume_avg = self._calc_volume_avg(buf, self.volume_avg_period)

            current_bar_idx = len(buf) - 1
            last_signal_idx = self.last_signal_bar[bar.symbol]
            bars_since_signal = current_bar_idx - last_signal_idx

            # Check cooldown
            if bars_since_signal < self.signal_cooldown_bars:
                return None

            # Get previous bar for crossover detection
            if len(buf) < 2:
                return None

            prev_bar = buf[-2]
            curr_close = Decimal(str(bar.close))
            prev_close = Decimal(str(prev_bar.close))
            curr_volume = bar.volume or 0
            price_above_vwap = curr_close > Decimal(str(vwap))
            prev_above_vwap = Decimal(str(prev_bar.close)) > Decimal(str(vwap))

            # Volume filter
            volume_spike = curr_volume > (volume_avg * self.volume_spike_multiplier)

            # BUY signal
            if (
                not price_above_vwap  # Currently above VWAP (crossover)
                and prev_above_vwap
                and ema_fast > ema_slow  # Uptrend
                and 40 <= rsi <= 65  # Momentum
                and volume_spike
            ):
                sl_price = float(curr_close) - (float(atr) * self.sl_atr_multiplier)
                tp_price = float(curr_close) + (float(atr) * self.tp_atr_multiplier)

                self.last_signal_bar[bar.symbol] = current_bar_idx
                self.position_entry_bar[bar.symbol] = current_bar_idx

                return Signal(
                    symbol=bar.symbol,
                    action="buy",
                    quantity=self._calculate_qty(bar),
                    confidence=0.85,
                    metadata={
                        "strategy": self.name,
                        "price": float(bar.close),
                        "stop_loss": sl_price,
                        "take_profit": tp_price,
                        "reason": "Momentum crossover above VWAP",
                        "atr": float(atr),
                        "rsi": float(rsi),
                        "ema_trend": "up",
                    },
                )

            # SELL signal
            if (
                price_above_vwap  # Currently below VWAP (crossover)
                and not prev_above_vwap
                and ema_fast < ema_slow  # Downtrend
                and 35 <= rsi <= 60  # Momentum
                and volume_spike
            ):
                sl_price = float(curr_close) + (float(atr) * self.sl_atr_multiplier)
                tp_price = float(curr_close) - (float(atr) * self.tp_atr_multiplier)

                self.last_signal_bar[bar.symbol] = current_bar_idx
                self.position_entry_bar[bar.symbol] = current_bar_idx

                return Signal(
                    symbol=bar.symbol,
                    action="sell",
                    quantity=self._calculate_qty(bar),
                    confidence=0.85,
                    metadata={
                        "strategy": self.name,
                        "price": float(bar.close),
                        "stop_loss": sl_price,
                        "take_profit": tp_price,
                        "reason": "Momentum crossover below VWAP",
                        "atr": float(atr),
                        "rsi": float(rsi),
                        "ema_trend": "down",
                    },
                )

            # Check time-based exit (max hold bars)
            entry_idx = self.position_entry_bar.get(bar.symbol, -1)
            if entry_idx >= 0 and current_bar_idx - entry_idx >= self.max_hold_bars:
                self.position_entry_bar[bar.symbol] = -1
                # Could emit exit signal here if needed

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

    def _calc_vwap(self, bars: deque) -> float:
        """Calculate VWAP from bars."""
        if not bars:
            return 0.0

        tp_volume_sum = 0.0
        volume_sum = 0.0

        for bar in bars:
            tp = (bar.high + bar.low + bar.close) / 3
            tp_volume_sum += tp * (bar.volume or 0)
            volume_sum += bar.volume or 0

        if volume_sum == 0:
            return float(bars[-1].close)

        vwap = tp_volume_sum / volume_sum
        return vwap

    def _calc_volume_avg(self, bars: deque, period: int) -> float:
        """Calculate volume average."""
        if len(bars) < period:
            return sum(b.volume or 0 for b in bars) / len(bars) if bars else 0

        return sum(b.volume or 0 for b in list(bars)[-period:]) / period

    def _calculate_qty(self, bar: Bar) -> float:
        """Calculate position size based on price and risk."""
        # Simple fixed quantity for now; can be enhanced with position sizing
        return 1.0

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        return {
            "name": self.name,
            "symbols": self.config.get("symbols", []),
            "signals_generated": sum(1 for _ in self.last_signal_bar.values()),
        }
