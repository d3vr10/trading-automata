# Portfolio & Risk Management

## Virtual Fences

Each bot operates within a **virtual fence** — a capital boundary that prevents one bot from consuming the entire account balance.

```
Account Balance: $100,000
  +-- Bot A (SigmaAlpha): $40,000 fence (hard)
  +-- Bot B (Momentum):   $30,000 fence (hard)
  +-- Bot C (BuyAndHold): $30,000 fence (soft)
```

**Hard fence:** Bot can never exceed its allocation. If it loses money, it trades with less. If it gains, profits stay within the fence until rebalanced.

**Soft fence:** Bot can borrow from unallocated capital. More flexible but requires monitoring.

## Allocation Types

Configured per bot in `bots.yaml`:

| Type | Meaning |
|---|---|
| `fixed` | Dollar amount (e.g., $10,000) |
| `percentage` | Percentage of account (e.g., 30%) |

Percentage allocations are computed at startup from the current account balance.

## Risk Controls

```yaml
risk:
  max_position_pct: 0.10      # No single position > 10% of allocation
  max_portfolio_risk: 0.02     # Total risk (unrealized loss) < 2% of allocation
  max_open_positions: 5        # No more than 5 simultaneous positions
```

The portfolio manager enforces these BEFORE executing any signal. A signal that would violate a risk rule is silently dropped (logged but not executed).

## Position Sizing

The portfolio manager determines *how much* to buy/sell based on:
1. Signal quantity (from strategy)
2. Available capital within the fence
3. Position size limits from risk config
4. Current exposure (existing positions)

The final quantity is the minimum of all these constraints.

## Key Concepts

- **Drawdown:** Peak-to-trough decline. A 20% drawdown means you lost 20% from your highest point. Risk rules exist to limit maximum drawdown.
- **Risk per trade:** How much you can lose if a trade goes against you. Typically 1-2% of portfolio per trade.
- **Diversification:** Spreading capital across strategies and symbols. The multi-bot architecture enforces this structurally.

## Deep Dive

- Van Tharp, *Trade Your Way to Financial Freedom* — position sizing and risk management
- Ralph Vince, *The Mathematics of Money Management* — Kelly criterion, optimal f
- Investopedia on position sizing: https://www.investopedia.com/terms/p/positionsizing.asp
