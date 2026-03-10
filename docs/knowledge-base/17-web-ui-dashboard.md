# Web UI Dashboard & Analytics

## Why Per-Account, Not Global?

Most beginner trading dashboards show a single "portfolio value" number that sums everything together. This is how brokerages display your account — because you have *one* account.

But multi-account platforms (3Commas, Cryptohopper, Shrimpy) don't work this way. When you run multiple bots across multiple brokers, a global sum hides critical information:

- Bot A is up $500 and Bot B is down $500 → global P&L shows $0, masking that Bot B is bleeding
- One bot's drawdown is 15% but the global drawdown looks fine because another bot is up
- You can't tell which bot is actually performing and which should be stopped

**The fix:** Per-account cards are the primary view. Each bot/account shows its own equity, P&L, win rate, drawdown, and sparkline. Global totals exist only as a compact summary row at the top — secondary information, not primary.

## Drawdown: The Most Important Metric You're Probably Ignoring

**Drawdown** is the peak-to-trough decline from a portfolio's highest value. If your account hit $10,000 and is now at $8,000, you have a 20% drawdown.

Why it matters more than P&L:
- A bot with +$1,000 P&L and 40% max drawdown is *worse* than a bot with +$500 P&L and 5% max drawdown
- Drawdown tells you how much pain you'd endure holding through the worst period
- Professional fund managers are evaluated by Sharpe ratio and max drawdown, not just returns

### High-Water Mark Approach

We track drawdown using a **high-water mark (HWM)** — the highest equity value ever recorded:

```
Time    Equity    HWM       Drawdown
  1     $10,000   $10,000   0%
  2     $10,500   $10,500   0%        ← new high
  3     $9,800    $10,500   6.67%     ← dropped from peak
  4     $10,200   $10,500   2.86%     ← recovering but still below peak
  5     $11,000   $11,000   0%        ← new high, drawdown resets
```

Formula: `drawdown_pct = (HWM - equity) / HWM × 100`

**When it's computed:** At snapshot persist time (hourly), not on every API request. This avoids expensive queries on reads — the cost is amortized into the write path where it's negligible.

**Where it's stored:** `portfolio_snapshots.high_water_mark` and `portfolio_snapshots.drawdown_pct` columns (migration 004).

### Dashboard Display

Two drawdown numbers per bot:
- **Current drawdown** — how far below the peak right now (red if > 5%)
- **Max drawdown** — worst drawdown ever recorded (red if > 10%)

These appear on both the dashboard per-account cards and the bot detail page.

## Real-Time Updates via WebSocket

The dashboard doesn't poll. It subscribes to three WebSocket events:

| Event | Triggered When | What Changes |
|-------|---------------|--------------|
| `bot_status_changed` | Bot started, stopped, paused | Status badges, active count |
| `trade_executed` | Trade opened or closed | P&L, win rate, recent trades |
| `account_snapshot` | Hourly snapshot persisted | Equity values, drawdown |

All three trigger the same action: reload all dashboard data. But they're **debounced at 500ms** — if 10 events arrive in rapid succession (e.g., bot starts and immediately executes trades), only one API call fires.

Why not granular updates? The dashboard makes 8 parallel API calls. The marginal cost of reloading everything vs. surgically updating one section is negligible, and it avoids complex state management bugs where sections get out of sync.

## Multi-Line Equity Chart

When you have multiple bots, you need to compare their equity trajectories on the same chart. A single-line chart per bot forces the user to mentally align timescales.

The multi-line sparkline renders all bot equity series on a **shared Y-axis** (global min/max), so you can instantly see:
- Which bot has the most capital
- Which bot is volatile vs. stable
- Convergence/divergence between accounts

Uses oklch colors for perceptual uniformity — all lines are equally visually prominent regardless of hue.

## Date Range Filtering

Trades and Analytics pages support `date_from` / `date_to` filters. The filter chain is:

```
Date picker (UI) → API client (query params) → FastAPI endpoint → SQL WHERE clause
```

Key decisions:
- **Filters reset pagination** — changing the date range sends you back to page 1
- **Clear button** only appears when a filter is active — no visual noise in the default state
- **Filters show in all states** — even during loading/empty, so the user can always adjust

## Trade Duration (Holding Time)

Average time between entry and exit, per bot. Computed as:

```sql
AVG(extract(epoch, exit_timestamp) - extract(epoch, entry_timestamp))
GROUP BY bot_name
```

Why this matters:
- A scalping bot should hold for minutes. If it's holding for days, something is wrong.
- A swing trading bot should hold for days. If it's closing in minutes, it's being stopped out too aggressively.
- Comparing expected vs. actual holding time is a quick health check.

Displayed as adaptive units: `23s`, `14m`, `2.5h`, `3.2d`.

## Dashboard Information Hierarchy

The layout follows a deliberate information hierarchy:

```
1. Global summary (glanceable)     ← "Am I up or down overall?"
2. Per-account cards (actionable)  ← "Which bot needs attention?"
3. Equity curves (trend)           ← "Where am I headed?"
4. Drawdown overview (risk)        ← "How much am I risking?"
5. Recent trades + bot status      ← "What just happened?"
6. Trade P&L sparkline (micro)     ← "Pattern in recent results?"
```

Each section answers a progressively more detailed question. A user scanning the dashboard moves naturally from overview to detail without needing to navigate away.

## Key Files

| Layer | File | Purpose |
|-------|------|---------|
| **Frontend** | `web-ui/src/app/[locale]/dashboard/page.tsx` | Main dashboard with per-account view |
| | `web-ui/src/app/[locale]/dashboard/bots/[id]/page.tsx` | Bot detail (drawdown, holding time) |
| | `web-ui/src/app/[locale]/dashboard/trades/page.tsx` | Trade history with date filters |
| | `web-ui/src/app/[locale]/dashboard/metrics/page.tsx` | Analytics with date filters |
| | `web-ui/src/components/charts/multi-line-sparkline.tsx` | Multi-series SVG chart |
| **API** | `api/app/routers/trades.py` | Trade/analytics endpoints with date params |
| | `api/app/routers/bots.py` | Bot stats, drawdown, per-bot history |
| **Service** | `api/app/services/trade_service.py` | Queries: analytics, duration, drawdown |
| | `api/app/services/bot_service.py` | Snapshot persistence with HWM computation |
| **Migration** | `shared/alembic/versions/004_add_drawdown_fields.py` | HWM + drawdown columns |

## Deep Dive

- Investopedia on drawdown: https://www.investopedia.com/terms/d/drawdown.asp
- High-water mark in hedge funds: https://www.investopedia.com/terms/h/highwatermark.asp
- Edward Tufte, *The Visual Display of Quantitative Information* — information density in dashboards
- Stephen Few, *Information Dashboard Design* — effective dashboard patterns
