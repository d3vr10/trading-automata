# Strategies & Signals

## The Strategy Interface

Every strategy extends `BaseStrategy` and implements one method:

```python
class BaseStrategy:
    def on_bar(self, bar: Bar) -> Optional[Signal]:
        """Given a new price bar, optionally return a trading signal."""
        ...
```

A `Bar` is a price candle: open, high, low, close, volume, timestamp.
A `Signal` is an instruction: buy/sell symbol X, quantity Y, confidence Z.

The strategy does NOT execute trades. It only produces signals. The portfolio manager decides whether to act on them (position limits, risk checks, capital availability).

## Strategy Registry

Strategies are registered by class name, then instantiated from YAML config:

```yaml
# config/strategies.yaml
strategies:
  - name: SigmaSeriesAlphaStrategy
    config:
      symbols: [AAPL, MSFT]
      lookback: 20
      threshold: 0.02
```

The registry maps `"SigmaSeriesAlphaStrategy"` -> the class, then calls `cls(config)`.

## Built-in Strategies

| Strategy | Logic | Timeframe |
|---|---|---|
| BuyAndHold | Buy once, never sell | Long-term |
| MeanReversion | Buy below moving average, sell above | Swing |
| Momentum | Follow trend direction with volume confirmation | Intraday |
| RSIATRTrend | RSI for entry, ATR for stop-loss sizing | Swing |
| SigmaFast | Quick mean-reversion with tight stops | Scalping |
| SigmaAlpha | Multi-factor with trend + momentum + volatility | Swing |
| SigmaAlphaBull | SigmaAlpha variant optimized for bull markets | Swing |

## Warm-Up

Strategies that use indicators (RSI, moving averages) need historical data before they can generate meaningful signals. The warm-up phase feeds historical bars to `on_bar()` before the live loop starts, so indicators are primed.

## Key Concepts

- **Technical indicators:** Mathematical transformations of price/volume data. RSI measures momentum (0-100), ATR measures volatility (average true range), moving averages smooth noise.
- **Signal confidence:** 0.0-1.0 score. Higher confidence = strategy is more certain. Portfolio manager can use this for position sizing.
- **Separation of concerns:** Strategy produces signals. Portfolio manager validates against risk rules. Order manager executes via broker. This prevents strategies from accidentally over-leveraging.

## Deep Dive

- pandas-ta library: https://github.com/twopirllc/pandas-ta (all indicator implementations)
- Investopedia on RSI: https://www.investopedia.com/terms/r/rsi.asp
- Investopedia on ATR: https://www.investopedia.com/terms/a/atr.asp
- Ernest Chan, *Quantitative Trading* — practical guide to building strategies
