# Strategy Filters: Volatility & Liquidity

## Overview

Filters prevent the trading bot from trading in unsuitable market conditions. They act as **pre-checks** that run **before** the strategy generates trading signals.

This implements best practices #2 (volatility bounds) and #3 (liquidity requirements).

## Filter Types

### 1. Liquidity Filter (min_volume)

**What it does**: Skips bars with insufficient trading volume.

**Why it matters**:
- Low volume = wide spreads = trading costs eat into profits
- Low volume = orders may not fill at desired price
- Low volume = may be unable to exit position quickly

**Configuration**:
```yaml
filters:
  min_volume: 500000  # Minimum units traded in bar
```

**Recommended Values**:
| Asset Class | Typical Range | Example |
|-------------|---------------|---------|
| Forex (Major) | 500K - 2M | 1M units |
| Stocks (Large Cap) | 1M - 10M | 2M shares |
| Crypto | 50K - 500K | 100K units |
| Commodities | 100K - 1M | 500K contracts |

**Example - When Filtering Occurs**:
```
Bar: EUR/USD H1
Volume: 250,000 units
min_volume: 500,000
Result: ❌ FILTERED OUT - Not enough volume
```

### 2. Volatility Filters (min_atr, max_atr)

**What it does**: Only trades when volatility is in a "sweet spot" range.

**Too Low (min_atr)**:
- Market is too calm
- Price moves are tiny
- Risk/reward ratio deteriorates
- Noise becomes significant

**Too High (max_atr)**:
- Market is too chaotic
- Stops become very wide
- Risk per trade becomes large
- Whipsaws more likely

**Configuration**:
```yaml
filters:
  min_atr: 30    # Minimum volatility acceptable
  max_atr: 200   # Maximum volatility acceptable
```

**Recommended Values by Asset**:

| Asset | Unit | Min ATR | Max ATR | Rationale |
|-------|------|---------|---------|-----------|
| **EUR/USD** | Pips | 25-40 | 150-250 | Normal FX volatility |
| **GBP/USD** | Pips | 30-50 | 200-300 | Bigger moves |
| **SPY** | $ | 0.3-0.8 | 2-5 | Stock moves in dollars |
| **QQQ** | $ | 0.5-1.5 | 3-8 | Tech more volatile |
| **BTC/USD** | $ | 100-500 | 2000-5000 | Crypto very volatile |

**Example - Filtering by Volatility**:
```
Bar 1: EUR/USD H1
ATR: 20 pips (calculated from last 14 bars)
min_atr: 30 pips
Result: ❌ FILTERED OUT - Too calm, not enough movement

Bar 2: EUR/USD H1
ATR: 100 pips
max_atr: 200 pips
Result: ✅ ALLOWED - Volatility in sweet spot

Bar 3: EUR/USD H1
ATR: 250 pips
max_atr: 200 pips
Result: ❌ FILTERED OUT - Too volatile, risk too high
```

## How Filters Work

### Execution Order
1. Strategy receives bar data
2. **BEFORE** calculating RSI, ATR, EMA:
   - Check volume >= min_volume ❌ Filter if fails
   - Calculate ATR to check volatility bounds
   - Check min_atr <= ATR <= max_atr ❌ Filter if fails
3. If passes all filters: Calculate indicators and generate signal

### Code Flow
```python
def on_bar(self, bar: Bar) -> Optional[Signal]:
    # ... initialize history ...

    # ✅ Apply filters FIRST (before any analysis)
    if not self.should_trade(bar):
        return None  # Skip this bar

    # Only if filters pass, calculate indicators
    indicators = self._calculate_indicators(bar.symbol)
    return self._generate_signal(bar, indicators)
```

## Configuration Examples

### Conservative (Low Risk)
```yaml
filters:
  min_volume: 1000000  # High volume requirement
  min_atr: 50          # Won't trade small moves
  max_atr: 100         # Won't trade big moves
  # Result: Trades only in calm, liquid conditions
```

### Balanced (Moderate)
```yaml
filters:
  min_volume: 500000   # Medium volume
  min_atr: 30          # Some movement needed
  max_atr: 200         # Reasonable max volatility
  # Result: Trades in most normal conditions
```

### Aggressive (High Volume)
```yaml
filters:
  min_volume: 100000   # Low volume okay
  min_atr: 10          # Even small moves okay
  max_atr: 500         # Accepts high volatility
  # Result: Trades frequently, higher risk
```

## Per-Asset-Class Configuration

### Forex (EUR/USD)
```yaml
- name: "rsi_atr_forex"
  class: "RSIATRTrendStrategy"
  symbols: ["EUR/USD"]
  parameters:
    position_size: 10
  filters:
    min_volume: 500000   # Forex needs volume
    min_atr: 30          # In pips
    max_atr: 200         # In pips
```

### Stocks (SPY)
```yaml
- name: "rsi_atr_stocks"
  class: "RSIATRTrendStrategy"
  symbols: ["SPY"]
  parameters:
    position_size: 50    # Shares
  filters:
    min_volume: 1000000  # Stocks need high volume
    min_atr: 0.5         # In dollars
    max_atr: 5.0         # In dollars
```

### Crypto (BTC/USD)
```yaml
- name: "rsi_atr_crypto"
  class: "RSIATRTrendStrategy"
  symbols: ["BTC/USD"]
  parameters:
    position_size: 0.05  # Bitcoin units
  filters:
    min_volume: 100000   # Crypto lower volume
    min_atr: 200         # In dollars
    max_atr: 3000        # Crypto very volatile
```

## Monitoring Filters

### Check How Many Bars Are Filtered
```bash
# View strategy statistics
docker-compose logs | grep "bars_analyzed\|bars_filtered"
```

Example output:
```
Strategy stats: bars_processed=100, bars_filtered_out=25, bars_analyzed=75
# = 25% of bars filtered out (not enough volume/volatility)
```

### Adjustment Guide
If **too many bars filtered** (>50%):
```yaml
# Make filters less strict
filters:
  min_volume: 250000  # Reduce from 500000
  min_atr: 15         # Reduce from 30
  max_atr: 300        # Increase from 200
```

If **too few bars filtered** (<5%):
```yaml
# Make filters stricter
filters:
  min_volume: 1000000  # Increase from 500000
  min_atr: 50          # Increase from 30
  max_atr: 100         # Decrease from 200
```

## Real-World Example

### Before Filters
```
Signal: BUY SPY @ 500
Volume: 50,000 shares (very low!)
ATR: 0.02 (too calm, almost no movement)
Result: ❌ Order placed anyway - WRONG!
        - Execution poor due to low volume
        - Move too small to overcome costs
        - Loss likely
```

### With Filters
```
Signal: BUY SPY @ 500
Check filters:
  - Volume 50,000 < min_volume 1,000,000 ❌
  - ATR 0.02 < min_atr 0.5 ❌
Result: ✅ Signal REJECTED
        - No order placed
        - Avoided bad trade
        - Saved money!
```

## Advanced: Dynamic Filters

You can adjust filters based on:
- **Market regime** (trending vs ranging)
- **Time of day** (different sessions)
- **Economic calendar** (avoid major news)
- **Recent volatility** (increase after spikes)

These are planned future enhancements. For now, use static filters that work across conditions.

## Filter Statistics

Each strategy tracks:
- **bars_processed**: Total bars received
- **bars_filtered_out**: Bars rejected by filters
- **bars_analyzed**: Bars that passed filters (bars_processed - bars_filtered_out)
- **filters_applied**: Whether any filters are active

View with:
```bash
grep "bars_analyzed\|bars_filtered" logs/trading_bot.log
```

## Best Practices

### ✅ DO
- Set min_volume based on typical volume for your symbols
- Tune min/max_atr based on historical volatility
- Test filters in paper trading before live
- Monitor filter statistics to ensure reasonable filtering
- Use asset-class-specific filter values

### ❌ DON'T
- Use same filters for forex and stocks (different units!)
- Set min_volume so high that no trades occur
- Set max_atr so low that you never trade
- Ignore filter statistics (they show market suitability)
- Change filters during live trading (wait for data)

## Troubleshooting

### Problem: Too Few Trades
**Check**:
1. Is min_atr too high?
   ```bash
   grep "ATR.*below min" logs/trading_bot.log | wc -l
   ```
   If many: Lower min_atr

2. Is min_volume too high?
   ```bash
   grep "min_volume" logs/trading_bot.log | wc -l
   ```
   If many: Lower min_volume

**Solution**:
```yaml
filters:
  min_volume: 250000  # Reduce
  min_atr: 20         # Reduce
```

### Problem: Too Many Losing Trades
**Check**:
1. Is max_atr too high (trading during chaos)?
2. Is min_volume too low (poor execution)?

**Solution**:
```yaml
filters:
  min_volume: 1000000  # Increase - require liquidity
  max_atr: 100         # Decrease - avoid chaos
```

### Problem: Can't Find Suitable Settings
**Start with**:
- Forex: min_volume=500K, min_atr=30, max_atr=200
- Stocks: min_volume=1M, min_atr=0.5, max_atr=3
- Crypto: min_volume=100K, min_atr=200, max_atr=2000

Then adjust based on results.

## Next Steps in Filter Development

Planned additions:
1. **Trend filter** - Only trade trending markets
2. **Economic calendar** - Avoid major news events
3. **Correlation filter** - Limit correlated positions
4. **Time filters** - Trading hours restrictions
5. **Session filters** - Trade only London, NY, Asian sessions

For now, implement #2 and #3 (volatility & liquidity) - they're the most important!
