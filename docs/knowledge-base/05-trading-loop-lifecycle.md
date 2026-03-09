# Trading Loop Lifecycle

## From Config to Execution

```
config/bots.yaml           config/strategies.yaml
      |                           |
      v                           v
 OrchestratorConfig         StrategyRegistry.load_from_config()
      |                           |
      v                           v
 BotOrchestrator.setup()    List[BaseStrategy]
      |
      v
 For each enabled bot:
   BotInstance(config, shared_db, shared_repo, ...)
      |
      v
   bot.setup()
     1. Create broker (Alpaca/Coinbase)
     2. Connect + verify credentials
     3. Create data provider
     4. Create order manager
     5. Create portfolio manager (virtual fence)
     6. Load + warm up strategies
      |
      v
   bot.start()
     -> _run_trading_loop()
```

## The Trading Loop (Simplified)

```python
while running:
    if broker disconnected:
        try reconnect with exponential backoff
        continue

    for symbol in all_strategy_symbols:
        bar = data_provider.get_latest_bar(symbol)
        for strategy in strategies:
            signal = strategy.on_bar(bar)      # EVALUATE
            if signal and not paused:
                order = portfolio.execute(signal)  # EXECUTE
                record_trade(order)                # RECORD

    update_metrics()
    sleep(poll_interval)
```

**Key insight:** The loop is synchronous *within* a bot but *concurrent across* bots. Each BotInstance runs as an asyncio Task inside the orchestrator.

## Timing

`poll_interval_minutes` in bot config controls how often the loop runs. Typical values:
- 1 min — for intraday strategies (scalping, momentum)
- 5-15 min — for swing strategies
- 60 min — for daily strategies

The interval is a *minimum* — if processing takes longer than the interval, the next iteration starts immediately after the current one finishes.

## Error Handling

- **Broker disconnect:** Exponential backoff (5s base, up to 80s), max 10 attempts
- **Bar fetch failure:** Log and skip that symbol, continue to next
- **Strategy exception:** Caught per-strategy, doesn't kill the loop
- **Unrecoverable:** Loop exits, bot enters stopped state, orchestrator detects via heartbeat

## Deep Dive

- Alpaca market data API: https://docs.alpaca.markets/docs/market-data-api
- asyncio Tasks: https://docs.python.org/3/library/asyncio-task.html
- For understanding market microstructure: Harris, *Trading and Exchanges* (Oxford)
