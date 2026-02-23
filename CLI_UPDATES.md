# CLI Updates for Multi-Bot Support

**Status:** ✅ Complete
**Date:** February 22, 2026

## What Changed

The CLI has been fully updated to support both **single-bot (legacy)** and **multi-bot** modes.

### Key Improvements

1. **Auto-detection**: CLI automatically detects if running in multi-bot mode
2. **Bot filtering**: All data commands now accept `--bot` option to filter by specific bot
3. **New commands**: Added `bots` and `bots-summary` for multi-bot management
4. **Backward compatible**: Legacy single-bot mode still works unchanged
5. **Enhanced output**: All tables now show `bot_name` column in multi-bot mode

---

## Updated Commands

### Configuration Commands

#### `trading-cli status [--bot BOT_NAME]`
Shows bot configuration and status.

**Legacy (single-bot):**
```bash
trading-cli status
```
Output: Broker, environment, risk parameters

**Multi-bot - List all bots:**
```bash
trading-cli status
```
Output: Table of all configured bots with status

**Multi-bot - Show specific bot:**
```bash
trading-cli status --bot alpha_bot
```
Output: Detailed config for alpha_bot

---

### Data Query Commands

All these commands now support `--bot` option:

#### `trading-cli trades [--bot BOT_NAME] [--symbol SYM] [--strategy STRAT] [--watch]`
View trades with optional bot filtering.

```bash
# All trades
trading-cli trades

# Trades for specific bot
trading-cli trades --bot momentum_bot

# Trades for specific bot and symbol
trading-cli trades --bot momentum_bot --symbol BTC-USD

# Watch for new trades (refreshes every 2s)
trading-cli trades --bot momentum_bot --watch
```

**Added column:** Bot name (tagged for each trade)

---

#### `trading-cli metrics [--bot BOT_NAME]`
Performance metrics (win rate, profit factor, etc.)

```bash
# Overall metrics
trading-cli metrics

# Metrics for specific bot
trading-cli metrics --bot conservative_bot
```

---

#### `trading-cli health [--bot BOT_NAME] [--watch]`
Health check status of brokers/strategies.

```bash
# All health checks
trading-cli health

# Health for specific bot
trading-cli health --bot bull_bot

# Watch mode (auto-refresh)
trading-cli health --bot bull_bot --watch
```

**Added column:** Bot name

---

#### `trading-cli positions [--bot BOT_NAME] [--watch]`
Show open positions.

```bash
# All open positions
trading-cli positions

# Open positions for specific bot
trading-cli positions --bot fast_bot
```

**Added column:** Bot name

---

#### `trading-cli summary [--bot BOT_NAME] [--watch]`
Quick overview of all metrics.

```bash
# Overall summary
trading-cli summary

# Summary for specific bot
trading-cli summary --bot alpha_bot --watch
```

---

#### `trading-cli events [--bot BOT_NAME] [--symbol SYM] [--type TYPE] [--severity SEVERITY] [--watch]`
View trading events and decisions.

```bash
# All events
trading-cli events

# Events for specific bot
trading-cli events --bot momentum_bot

# Events for specific bot and symbol
trading-cli events --bot momentum_bot --symbol BTC-USD

# Only errors
trading-cli events --bot momentum_bot --severity ERROR
```

**Added column:** Bot name

---

### New Multi-Bot Commands

#### `trading-cli bots [--watch]`
List all configured bots with status and statistics.

```bash
trading-cli bots
```

Output:
```
🤖 Multi-Bot Configuration
====================================================================================================
Total bots: 3

| Bot Name          | Status          | Broker  | Allocation | Trades | Open | Health           |
|-------------------|-----------------|---------|------------|--------|------|------------------|
| momentum_bot      | ✅ ENABLED      | COINBASE | $300.00   | 15     | 2    | 🟢 HEALTHY       |
| conservative_bot  | ✅ ENABLED      | COINBASE | $500.00   | 42     | 1    | 🟢 HEALTHY       |
| bull_bot          | ⏸️  DISABLED     | COINBASE | $1000.00  | 0      | 0    | ⚠️  DEGRADED     |
```

---

#### `trading-cli bots-summary`
Overall summary across all bots.

```bash
trading-cli bots-summary
```

Output:
```
📊 Multi-Bot Summary
============================================================
Total Bots                    3
Enabled Bots                  2
Total Capital Allocated       $1,800.00
Total Trades                  57
Open Positions                3
Overall Win Rate              56.1%
Profit Factor                 1.65
```

---

## Example Usage Scenarios

### Scenario 1: Monitor Single Momentum Bot

```bash
# Check status
trading-cli status --bot momentum_bot

# View recent trades
trading-cli trades --bot momentum_bot --limit 20

# Watch performance metrics
trading-cli metrics --bot momentum_bot --watch

# Check for errors
trading-cli events --bot momentum_bot --severity ERROR
```

---

### Scenario 2: Compare Two Bots' Performance

```bash
# Bot 1 summary
trading-cli summary --bot alpha_bot

# Bot 2 summary
trading-cli summary --bot beta_bot

# Side-by-side trade comparison
trading-cli trades --bot alpha_bot --limit 10
trading-cli trades --bot beta_bot --limit 10
```

---

### Scenario 3: Troubleshoot Issues

```bash
# See all health checks
trading-cli health

# Check specific bot's health
trading-cli health --bot problematic_bot

# View all errors
trading-cli events --severity ERROR

# View all errors for specific bot
trading-cli events --bot problematic_bot --severity ERROR

# Monitor in real-time
trading-cli events --bot problematic_bot --severity ERROR --watch
```

---

### Scenario 4: Overall System Status

```bash
# Quick overview
trading-cli bots-summary

# Detailed view of all bots
trading-cli bots

# Total trades and positions
trading-cli summary

# Overall metrics
trading-cli metrics
```

---

## Implementation Details

### Database Filtering

All commands now use bot_name filtering at the SQL level (efficient):

```python
# Legacy: no filtering
stmt = select(Trade).order_by(Trade.entry_timestamp.desc()).limit(10)

# Multi-bot: optional filtering
if bot:
    stmt = stmt.where(Trade.bot_name == bot)
```

### Mode Detection

CLI auto-detects mode:

```python
def detect_multi_bot_mode() -> bool:
    return (
        Path("config/bots.yaml").exists()
        or Path("config/bots").is_dir()
        or os.environ.get("BOT_MODE", "").lower() == "multi"
    )
```

### Backward Compatibility

- If no `config/bots.yaml` → Uses legacy `Settings` class
- If `config/bots.yaml` exists → Uses multi-bot config loader
- All old commands still work without `--bot` option

---

## Modified Files

**File:** `trading_bot/cli.py`
- Added imports: `Path`, `load_bot_configs`
- Added functions: `detect_multi_bot_mode()`, updated `get_database()`, `get_database_url()`
- Updated commands: `status`, `trades`, `metrics`, `health`, `positions`, `summary`, `events`
  - Added `--bot` option to all
  - Added bot_name filtering to queries
  - Added bot_name column to tables
- New commands: `bots`, `bots-summary`

---

## Testing the CLI

### Test Multi-Bot Mode Detection

```bash
# Check if multi-bot mode detected
trading-cli status

# Should show either:
# "🤖 Trading Bot Status (Multi-Bot Mode)" - if config/bots.yaml exists
# "🤖 Trading Bot Status (Legacy Single-Bot Mode)" - if not
```

### Test Bot Filtering

```bash
# List bots
trading-cli bots

# Get status of first bot (from output above)
trading-cli status --bot <bot_name>

# Check its trades
trading-cli trades --bot <bot_name>

# Check its metrics
trading-cli metrics --bot <bot_name>
```

### Test with Watch Mode

```bash
# Watch trades in real-time
trading-cli trades --watch

# Watch specific bot's trades
trading-cli trades --bot momentum_bot --watch

# Press Ctrl+C to stop
```

---

## All CLI Commands at a Glance

| Command | Purpose | Multi-Bot Support |
|---------|---------|-------------------|
| `status` | Bot configuration | ✅ --bot option |
| `trades` | Recent trades | ✅ --bot option |
| `metrics` | Performance metrics | ✅ --bot option |
| `health` | Bot health status | ✅ --bot option |
| `positions` | Open positions | ✅ --bot option |
| `summary` | Quick overview | ✅ --bot option |
| `events` | Event log | ✅ --bot option |
| `bots` | **NEW** List all bots | ✅ Multi-bot only |
| `bots-summary` | **NEW** Multi-bot summary | ✅ Multi-bot only |
| `broker-positions` | Live account positions | ⚠️ Broker-wide |
| `broker-orders` | Live account orders | ⚠️ Broker-wide |
| `close-position` | Close broker position | ⚠️ Broker-wide |
| `cancel-order` | Cancel broker order | ⚠️ Broker-wide |
| `schema` | Database table schema | ✅ Full support |
| `query` | Custom SQL queries | ✅ Full support |
| `version` | Show version | ✅ No changes |
| `uptime` | Bot uptime | ⚠️ Latest session |

**Legend:**
- ✅ = Full multi-bot support
- ⚠️ = Partial (affects all or latest)
- (Broker commands work at account level, not bot level)

---

## Summary

✅ All CLI commands updated to support multi-bot mode
✅ Auto-detection of single vs multi-bot mode
✅ 100% backward compatible with legacy single-bot deployments
✅ New commands for multi-bot management
✅ Efficient database filtering by bot_name
✅ Clear output showing bot names and status

**Ready for production deployment!**
