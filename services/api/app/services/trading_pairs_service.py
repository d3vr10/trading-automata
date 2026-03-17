"""Trading pairs catalog per broker type.

Returns available trading symbols for each supported broker.
Uses curated lists of popular, liquid assets to avoid overwhelming
users with thousands of obscure pairs.
"""

# Popular crypto pairs on Coinbase (base symbol only — engine appends -USD)
COINBASE_PAIRS = [
    {"symbol": "BTC", "name": "Bitcoin", "quote": "USD"},
    {"symbol": "ETH", "name": "Ethereum", "quote": "USD"},
    {"symbol": "SOL", "name": "Solana", "quote": "USD"},
    {"symbol": "XRP", "name": "XRP", "quote": "USD"},
    {"symbol": "DOGE", "name": "Dogecoin", "quote": "USD"},
    {"symbol": "ADA", "name": "Cardano", "quote": "USD"},
    {"symbol": "AVAX", "name": "Avalanche", "quote": "USD"},
    {"symbol": "LINK", "name": "Chainlink", "quote": "USD"},
    {"symbol": "DOT", "name": "Polkadot", "quote": "USD"},
    {"symbol": "MATIC", "name": "Polygon", "quote": "USD"},
    {"symbol": "UNI", "name": "Uniswap", "quote": "USD"},
    {"symbol": "ATOM", "name": "Cosmos", "quote": "USD"},
    {"symbol": "LTC", "name": "Litecoin", "quote": "USD"},
    {"symbol": "BCH", "name": "Bitcoin Cash", "quote": "USD"},
    {"symbol": "NEAR", "name": "NEAR Protocol", "quote": "USD"},
    {"symbol": "APT", "name": "Aptos", "quote": "USD"},
    {"symbol": "ARB", "name": "Arbitrum", "quote": "USD"},
    {"symbol": "OP", "name": "Optimism", "quote": "USD"},
    {"symbol": "FIL", "name": "Filecoin", "quote": "USD"},
    {"symbol": "AAVE", "name": "Aave", "quote": "USD"},
    {"symbol": "MKR", "name": "Maker", "quote": "USD"},
    {"symbol": "SUI", "name": "Sui", "quote": "USD"},
    {"symbol": "SEI", "name": "Sei", "quote": "USD"},
    {"symbol": "SHIB", "name": "Shiba Inu", "quote": "USD"},
    {"symbol": "PEPE", "name": "Pepe", "quote": "USD"},
]

# Popular stocks/ETFs on Alpaca
ALPACA_PAIRS = [
    {"symbol": "SPY", "name": "S&P 500 ETF", "quote": "USD"},
    {"symbol": "QQQ", "name": "Nasdaq 100 ETF", "quote": "USD"},
    {"symbol": "AAPL", "name": "Apple", "quote": "USD"},
    {"symbol": "MSFT", "name": "Microsoft", "quote": "USD"},
    {"symbol": "GOOGL", "name": "Alphabet", "quote": "USD"},
    {"symbol": "AMZN", "name": "Amazon", "quote": "USD"},
    {"symbol": "NVDA", "name": "NVIDIA", "quote": "USD"},
    {"symbol": "META", "name": "Meta Platforms", "quote": "USD"},
    {"symbol": "TSLA", "name": "Tesla", "quote": "USD"},
    {"symbol": "AMD", "name": "AMD", "quote": "USD"},
    {"symbol": "IWM", "name": "Russell 2000 ETF", "quote": "USD"},
    {"symbol": "DIA", "name": "Dow Jones ETF", "quote": "USD"},
    {"symbol": "GLD", "name": "Gold ETF", "quote": "USD"},
    {"symbol": "TLT", "name": "20+ Year Treasury ETF", "quote": "USD"},
    {"symbol": "COIN", "name": "Coinbase Global", "quote": "USD"},
]

BROKER_PAIRS: dict[str, list[dict]] = {
    "coinbase": COINBASE_PAIRS,
    "alpaca": ALPACA_PAIRS,
}


def get_trading_pairs(broker_type: str) -> list[dict]:
    """Return available trading pairs for a broker type."""
    return BROKER_PAIRS.get(broker_type.lower(), [])
