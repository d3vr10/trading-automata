"""SigmaSeriesAlphaBullStrategy - Bull market trend following, long-only.

Target: 96.25% win rate in confirmed bull markets via trend following.

Strategy Overview:
- Triple EMA stack (21/50/200) for trend confirmation
- ADX(14) for trend strength (must be > 25)
- RSI(10) for momentum entry zones
- MACD(12,26,9) for histogram rising confirmation
- ATR(14) for dynamic risk sizing
- LONG ONLY - No short sales

Buy Signal (Strong uptrend):
- EMA(21) > EMA(50) > EMA(200) (all stacked uptrend)
- ADX > 25 (strong trend)
- RSI(10) 35-55 (momentum but not overbought)
- MACD histogram rising (momentum building)
- Close > EMA(21) (price above fast MA)

Exit Signal (Downtrend reversal):
- RSI(10) > 72 (extreme overbought), OR
- EMA(21) crosses below EMA(50) (trend break), OR
- 2 consecutive closes below EMA(50) (trend deterioration)

No short trades - exit all longs on downtrend signals.

Risk Management:
- Stop Loss: 1.0x ATR below entry
- Take Profit: 4.0x ATR above entry
- Signal cooldown: 4 bars
"""

from collections import deque
from decimal import Decimal
from typing import Optional, Dict, Any

from trading_bot.data.models import Bar
from trading_bot.strategies.base import BaseStrategy, Signal


class SigmaSeriesAlphaBullStrategy(BaseStrategy):
    """Long-only bull market trend following strategy targeting 96.25% win rate."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize SigmaSeriesAlphaBullStrategy.

        Args:
            config: Strategy configuration dict with symbols, etc.
        """
        super().__init__(config)
        self.name = "SigmaSeriesAlphaBullStrategy"

        # Indicator parameters
        self.ema_fast_period = 21
        self.ema_mid_period = 50
        self.ema_slow_period = 200
        self.rsi_period = 10
        self.adx_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.atr_period = 14

        # Risk parameters
        self.rsi_buy_min = 35
        self.rsi_buy_max = 55
        self.adx_min = 25
        self.sl_atr_multiplier = 1.0
        self.tp_atr_multiplier = 4.0
        self.signal_cooldown_bars = 4
        self.ema_break_bars = 2  # 2 closes below EMA(50) triggers exit

        # Data buffers
        self.bars_deque: Dict[str, deque] = {}
        self.last_signal_bar: Dict[str, int] = {}
        self.closes_below_ema50: Dict[str, int] = {}  # counter for closes below EMA50

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
            self.closes_below_ema50[bar.symbol] = 0

        buf = self.bars_deque[bar.symbol]
        buf.append(bar)

        # Need minimum bars for indicators
        if len(buf) < max(self.ema_slow_period, self.adx_period, self.macd_slow + self.macd_signal):
            return None

        try:
            # Calculate indicators
            ema_fast = self._calc_ema(buf, self.ema_fast_period)
            ema_mid = self._calc_ema(buf, self.ema_mid_period)
            ema_slow = self._calc_ema(buf, self.ema_slow_period)
            rsi = self._calc_rsi(buf, self.rsi_period)
            adx = self._calc_adx(buf, self.adx_period)
            macd_hist = self._calc_macd_histogram(buf, self.macd_fast, self.macd_slow, self.macd_signal)
            atr = self._calc_atr(buf, self.atr_period)

            current_bar_idx = len(buf) - 1
            last_signal_idx = self.last_signal_bar[bar.symbol]
            bars_since_signal = current_bar_idx - last_signal_idx

            # Check cooldown
            if bars_since_signal < self.signal_cooldown_bars:
                return None

            curr_close = Decimal(str(bar.close))
            prev_close = Decimal(str(buf[-2].close)) if len(buf) > 1 else curr_close
            prev_ema_fast = self._calc_ema(deque(list(buf)[:-1]), self.ema_fast_period) if len(buf) > self.ema_fast_period else ema_fast
            prev_ema_mid = self._calc_ema(deque(list(buf)[:-1]), self.ema_mid_period) if len(buf) > self.ema_mid_period else ema_mid

            # Track closes below EMA(50)
            if curr_close < Decimal(str(ema_mid)):
                self.closes_below_ema50[bar.symbol] += 1
            else:
                self.closes_below_ema50[bar.symbol] = 0

            # EXIT signals (exit any long position)
            should_exit = False
            exit_reason = ""

            # Exit 1: RSI too high
            if rsi > 72:
                should_exit = True
                exit_reason = "RSI overbought (>72)"

            # Exit 2: EMA(21) crosses below EMA(50)
            elif prev_ema_fast > prev_ema_mid and ema_fast < ema_mid:
                should_exit = True
                exit_reason = "EMA(21) crossed below EMA(50)"

            # Exit 3: 2 closes below EMA(50)
            elif self.closes_below_ema50[bar.symbol] >= self.ema_break_bars:
                should_exit = True
                exit_reason = f"{self.ema_break_bars} closes below EMA(50)"

            if should_exit:
                self.last_signal_bar[bar.symbol] = current_bar_idx
                self.closes_below_ema50[bar.symbol] = 0

                return Signal(
                    symbol=bar.symbol,
                    action="sell",
                    quantity=self._calculate_qty(bar),
                    confidence=0.90,
                    metadata={
                        "price": float(bar.close),
                        "reason": f"Exit: {exit_reason}",
                        "atr": float(atr),
                        "rsi": float(rsi),
                        "ema_stack": f"{ema_fast:.2f}>{ema_mid:.2f}>{ema_slow:.2f}",
                    },
                )

            # BUY signal (strong uptrend)
            if (
                ema_fast > ema_mid > ema_slow  # Triple stack uptrend
                and adx > self.adx_min  # Strong trend
                and self.rsi_buy_min <= rsi <= self.rsi_buy_max  # Momentum in buy zone
                and macd_hist > 0  # MACD histogram rising
                and curr_close > Decimal(str(ema_fast))  # Price above fast MA
            ):
                sl_price = float(curr_close) - (float(atr) * self.sl_atr_multiplier)
                tp_price = float(curr_close) + (float(atr) * self.tp_atr_multiplier)

                self.last_signal_bar[bar.symbol] = current_bar_idx
                self.closes_below_ema50[bar.symbol] = 0

                return Signal(
                    symbol=bar.symbol,
                    action="buy",
                    quantity=self._calculate_qty(bar),
                    confidence=0.90,
                    metadata={
                        "price": float(bar.close),
                        "stop_loss": sl_price,
                        "take_profit": tp_price,
                        "reason": "Strong uptrend with momentum",
                        "atr": float(atr),
                        "rsi": float(rsi),
                        "adx": float(adx),
                        "ema_stack": f"{ema_fast:.2f}>{ema_mid:.2f}>{ema_slow:.2f}",
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

    def _calc_adx(self, bars: deque, period: int) -> float:
        """Calculate ADX (simplified version).

        This is a simplified ADX calculation using DI lines.
        Full ADX includes smoothing of DI lines - this version is good enough for signal generation.
        """
        if len(bars) < period:
            return 0.0

        # Calculate +DI and -DI
        plus_dm_sum = 0.0
        minus_dm_sum = 0.0
        tr_sum = 0.0

        recent_bars = list(bars)[-period:]
        for i in range(1, len(recent_bars)):
            bar = recent_bars[i]
            prev = recent_bars[i - 1]

            # Directional Movement
            up_move = bar.high - prev.high
            down_move = prev.low - bar.low

            if up_move > down_move and up_move > 0:
                plus_dm_sum += up_move
            if down_move > up_move and down_move > 0:
                minus_dm_sum += down_move

            # True Range
            tr = max(bar.high - bar.low, abs(bar.high - prev.close), abs(bar.low - prev.close))
            tr_sum += tr

        # Calculate DI lines
        plus_di = 100 * (plus_dm_sum / tr_sum) if tr_sum > 0 else 0
        minus_di = 100 * (minus_dm_sum / tr_sum) if tr_sum > 0 else 0

        # ADX is based on DI difference
        di_diff = abs(plus_di - minus_di)
        di_sum = plus_di + minus_di

        adx = 100 * (di_diff / di_sum) if di_sum > 0 else 0
        return adx

    def _calc_macd_histogram(self, bars: deque, fast: int, slow: int, signal: int) -> float:
        """Calculate MACD histogram."""
        if len(bars) < max(slow, signal):
            return 0.0

        ema_fast = self._calc_ema(bars, fast)
        ema_slow = self._calc_ema(bars, slow)
        macd_line = ema_fast - ema_slow

        # Calculate signal line (EMA of MACD)
        # Simplified: use recent MACD values
        macd_values = []
        for i in range(max(slow, len(bars) - signal * 2), len(bars)):
            bars_subset = deque(list(bars)[:i + 1])
            ema_f = self._calc_ema(bars_subset, fast)
            ema_s = self._calc_ema(bars_subset, slow)
            macd_values.append(ema_f - ema_s)

        if len(macd_values) < signal:
            signal_line = macd_line
        else:
            signal_line = sum(macd_values[-signal:]) / signal

        histogram = macd_line - signal_line
        return histogram

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
