"""SigmaSeriesAlphaBullCryptoStrategy - Crypto-tuned bull market trend following.

Adapted from SigmaAlphaBull with parameters tuned for cryptocurrency volatility:
- Wider RSI buy zone (25-50) — crypto trends harder and faster
- Higher RSI exit (78) — crypto stays overbought longer in bull runs
- Lower ADX threshold (20) — crypto trends are noisier but still valid
- Wider ATR stops (1.5x) — crypto swings 3-5x more than stocks intraday
- Bigger ATR target (5x) — let crypto winners run
- 3 closes below EMA50 (vs 2) — give crypto more room before exit
- Longer cooldown (6 bars) — avoid whipsaws in volatile markets

Buy Signal:
- EMA(21) > EMA(50) > EMA(200)
- ADX > 20
- RSI(10) in 25-50 zone
- MACD histogram > 0
- Close > EMA(21)

Exit Signal:
- RSI(10) > 78 (extreme overbought), OR
- EMA(21) crosses below EMA(50), OR
- 3 consecutive closes below EMA(50)

Risk Management:
- Stop Loss: 1.5x ATR below entry
- Take Profit: 5.0x ATR above entry
- Signal cooldown: 6 bars
"""

from collections import deque
from decimal import Decimal
from typing import Optional, Dict, Any

from trading_automata.data.models import Bar, Quote
from trading_automata.monitoring.event_logger import EventLogger
from trading_automata.strategies.base import BaseStrategy, Signal

import logging

logger = logging.getLogger(__name__)


class SigmaSeriesAlphaBullCryptoStrategy(BaseStrategy):
    """Crypto-tuned long-only bull market trend following strategy."""

    def __init__(self, name: str, config: Dict[str, Any], event_logger: Optional[EventLogger] = None):
        super().__init__(name, config, event_logger)

        # Indicator parameters (same structure, crypto-tuned values)
        self.ema_fast_period = 21
        self.ema_mid_period = 50
        self.ema_slow_period = 200
        self.rsi_period = 10
        self.adx_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.atr_period = 14

        # Crypto-tuned risk parameters
        self.rsi_buy_min = 25       # Wider: crypto can buy at lower RSI
        self.rsi_buy_max = 50       # Tighter top: avoid chasing
        self.rsi_exit = 78          # Higher: crypto stays overbought longer
        self.adx_min = 20           # Lower: crypto trends are noisier
        self.sl_atr_multiplier = 1.5  # Wider stops for crypto volatility
        self.tp_atr_multiplier = 5.0  # Let winners run in crypto
        self.signal_cooldown_bars = 6  # Longer cooldown to avoid whipsaws
        self.ema_break_bars = 3     # 3 closes below EMA50 before exit

        # Data buffers
        self.bars_deque: Dict[str, deque] = {}
        self.last_signal_bar: Dict[str, int] = {}
        self.closes_below_ema50: Dict[str, int] = {}

        # Position tracking: symbol -> 'long' or None
        self._position_state: Dict[str, Optional[str]] = {}

        self.max_buffer_size = 250

    def on_bar(self, bar: Bar) -> Optional[Signal]:
        """Process a bar and generate trading signal."""
        if bar.symbol not in self.bars_deque:
            self.bars_deque[bar.symbol] = deque(maxlen=self.max_buffer_size)
            self.last_signal_bar[bar.symbol] = -self.signal_cooldown_bars - 1
            self.closes_below_ema50[bar.symbol] = 0
            self._position_state[bar.symbol] = None

        buf = self.bars_deque[bar.symbol]
        buf.append(bar)

        if len(buf) < max(self.ema_slow_period, self.adx_period, self.macd_slow + self.macd_signal):
            return None

        try:
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

            if bars_since_signal < self.signal_cooldown_bars:
                return None

            curr_close = Decimal(str(bar.close))
            prev_ema_fast = self._calc_ema(deque(list(buf)[:-1]), self.ema_fast_period) if len(buf) > self.ema_fast_period else ema_fast
            prev_ema_mid = self._calc_ema(deque(list(buf)[:-1]), self.ema_mid_period) if len(buf) > self.ema_mid_period else ema_mid

            # Track closes below EMA(50)
            if curr_close < Decimal(str(ema_mid)):
                self.closes_below_ema50[bar.symbol] += 1
            else:
                self.closes_below_ema50[bar.symbol] = 0

            in_position = self._position_state.get(bar.symbol) == 'long'

            # EXIT signals
            should_exit = False
            exit_reason = ""

            if in_position and rsi > self.rsi_exit:
                should_exit = True
                exit_reason = f"RSI overbought (>{self.rsi_exit})"

            elif in_position and prev_ema_fast > prev_ema_mid and ema_fast < ema_mid:
                should_exit = True
                exit_reason = "EMA(21) crossed below EMA(50)"

            elif in_position and self.closes_below_ema50[bar.symbol] >= self.ema_break_bars:
                should_exit = True
                exit_reason = f"{self.ema_break_bars} closes below EMA(50)"

            if should_exit:
                self.last_signal_bar[bar.symbol] = current_bar_idx
                self.closes_below_ema50[bar.symbol] = 0
                self._position_state[bar.symbol] = None

                return Signal(
                    symbol=bar.symbol,
                    action="sell",
                    quantity=self._calculate_qty(bar),
                    confidence=0.90,
                    metadata={
                        "strategy": self.name,
                        "price": float(bar.close),
                        "reason": f"Exit: {exit_reason}",
                        "atr": float(atr),
                        "rsi": float(rsi),
                        "ema_stack": f"{ema_fast:.2f}>{ema_mid:.2f}>{ema_slow:.2f}",
                    },
                )

            # BUY signal
            if not in_position and (
                ema_fast > ema_mid > ema_slow
                and adx > self.adx_min
                and self.rsi_buy_min <= rsi <= self.rsi_buy_max
                and macd_hist > 0
                and curr_close > Decimal(str(ema_fast))
            ):
                sl_price = float(curr_close) - (float(atr) * self.sl_atr_multiplier)
                tp_price = float(curr_close) + (float(atr) * self.tp_atr_multiplier)

                self.last_signal_bar[bar.symbol] = current_bar_idx
                self.closes_below_ema50[bar.symbol] = 0
                self._position_state[bar.symbol] = 'long'

                return Signal(
                    symbol=bar.symbol,
                    action="buy",
                    quantity=self._calculate_qty(bar),
                    confidence=0.90,
                    metadata={
                        "strategy": self.name,
                        "price": float(bar.close),
                        "stop_loss": sl_price,
                        "take_profit": tp_price,
                        "reason": "Strong crypto uptrend with momentum",
                        "atr": float(atr),
                        "rsi": float(rsi),
                        "adx": float(adx),
                        "ema_stack": f"{ema_fast:.2f}>{ema_mid:.2f}>{ema_slow:.2f}",
                    },
                )

        except Exception as e:
            logger.error(f"Error processing bar for {bar.symbol}: {e}")

        return None

    def on_quote(self, quote: Quote) -> Optional[Signal]:
        return None

    def validate_config(self) -> bool:
        symbols = self.config.get('symbols', [])
        if not symbols:
            logger.error("No symbols configured")
            return False
        return True

    def _calc_ema(self, bars: deque, period: int) -> float:
        if len(bars) < period:
            return float(bars[-1].close)
        multiplier = 2.0 / (period + 1)
        ema = float(bars[0].close)
        for bar in list(bars)[1:]:
            ema = float(bar.close) * multiplier + ema * (1 - multiplier)
        return ema

    def _calc_rsi(self, bars: deque, period: int) -> float:
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
        return 100 - (100 / (1 + rs))

    def _calc_adx(self, bars: deque, period: int) -> float:
        if len(bars) < period:
            return 0.0
        plus_dm_sum = 0.0
        minus_dm_sum = 0.0
        tr_sum = 0.0
        recent_bars = list(bars)[-period:]
        for i in range(1, len(recent_bars)):
            bar = recent_bars[i]
            prev = recent_bars[i - 1]
            up_move = bar.high - prev.high
            down_move = prev.low - bar.low
            if up_move > down_move and up_move > 0:
                plus_dm_sum += up_move
            if down_move > up_move and down_move > 0:
                minus_dm_sum += down_move
            tr = max(bar.high - bar.low, abs(bar.high - prev.close), abs(bar.low - prev.close))
            tr_sum += tr
        plus_di = 100 * (plus_dm_sum / tr_sum) if tr_sum > 0 else 0
        minus_di = 100 * (minus_dm_sum / tr_sum) if tr_sum > 0 else 0
        di_diff = abs(plus_di - minus_di)
        di_sum = plus_di + minus_di
        return 100 * (di_diff / di_sum) if di_sum > 0 else 0

    def _calc_macd_histogram(self, bars: deque, fast: int, slow: int, signal: int) -> float:
        if len(bars) < max(slow, signal):
            return 0.0
        ema_fast = self._calc_ema(bars, fast)
        ema_slow = self._calc_ema(bars, slow)
        macd_line = ema_fast - ema_slow
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
        return macd_line - signal_line

    def _calc_atr(self, bars: deque, period: int) -> float:
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
        return sum(trs[-period:]) / period if trs else 0

    def _calculate_qty(self, bar: Bar) -> float:
        return float(self.config.get('position_size', 1.0))

    def get_stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "symbols": self.config.get("symbols", []),
            "signals_generated": sum(1 for _ in self.last_signal_bar.values()),
        }
