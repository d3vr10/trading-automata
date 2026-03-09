# Broker Abstraction

## The Interface

All brokers implement `IBroker`:

```python
class IBroker:
    def connect() -> bool
    def disconnect()
    def get_account() -> AccountInfo
    def submit_order(symbol, qty, side, order_type) -> str  # returns order_id
    def get_order(order_id) -> OrderInfo
    def cancel_order(order_id) -> bool
    def get_positions() -> List[Position]
```

The trading loop never calls Alpaca or Coinbase directly — it calls `self.broker.submit_order()`. Swapping brokers is a config change, not a code change.

## Supported Brokers

| Broker | Asset class | Environments | Rate Limit |
|---|---|---|---|
| Alpaca | US stocks, options | paper, live | 200 req/min per API key |
| Coinbase | Crypto | sandbox, live | 30 req/s per user |

## Environment Isolation

```yaml
broker:
  type: alpaca
  environment: paper  # or "live"
  api_key: ${ALPACA_API_KEY}
  secret_key: ${ALPACA_SECRET_KEY}
```

`paper` and `live` environments use different API endpoints. The factory creates the correct client based on the environment string. This prevents accidentally trading real money during development.

## Rate Limits

Rate limits are **per API key** (Alpaca) or **per user** (Coinbase), NOT per IP. This means:
- Multiple bots sharing one API key share the rate limit
- Multiple users each have their own limit (isolated)
- The platform doesn't need centralized rate limiting for broker calls

Current approach: the poll interval naturally stays well under limits. If broker calls fail with 429, the reconnect backoff handles retry.

## Factory Pattern

```python
broker = BrokerFactory.create_broker(
    broker_type="alpaca",
    environment=Environment.PAPER,
    config={"api_key": "...", "secret_key": "..."},
)
```

The factory maps string names to classes. Adding a new broker = implement IBroker + register in factory.

## Deep Dive

- Alpaca API docs: https://docs.alpaca.markets/
- Coinbase Advanced Trade API: https://docs.cdp.coinbase.com/advanced-trade/docs/welcome
- GoF Factory pattern: https://refactoring.guru/design-patterns/factory-method
