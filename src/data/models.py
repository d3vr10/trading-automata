from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class Bar:
    """Bar data for a given timeframe."""
    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    def __post_init__(self):
        """Validate bar data."""
        if self.high < self.low:
            raise ValueError(f"High ({self.high}) cannot be less than low ({self.low})")
        if self.open < 0 or self.high < 0 or self.low < 0 or self.close < 0:
            raise ValueError("Prices cannot be negative")


@dataclass
class Quote:
    """Real-time quote data."""
    symbol: str
    timestamp: datetime
    bid_price: Decimal
    ask_price: Decimal
    bid_size: int
    ask_size: int

    def __post_init__(self):
        """Validate quote data."""
        if self.bid_price > self.ask_price:
            raise ValueError(f"Bid price ({self.bid_price}) cannot be greater than ask price ({self.ask_price})")
        if self.bid_size < 0 or self.ask_size < 0:
            raise ValueError("Sizes cannot be negative")

    @property
    def mid_price(self) -> Decimal:
        """Get mid price between bid and ask."""
        return (self.bid_price + self.ask_price) / 2

    @property
    def spread(self) -> Decimal:
        """Get spread between bid and ask."""
        return self.ask_price - self.bid_price


@dataclass
class Trade:
    """Trade execution data."""
    symbol: str
    timestamp: datetime
    price: Decimal
    size: int
    side: str  # 'buy' or 'sell'

    def __post_init__(self):
        """Validate trade data."""
        if self.price < 0:
            raise ValueError("Price cannot be negative")
        if self.size <= 0:
            raise ValueError("Size must be positive")
        if self.side not in ('buy', 'sell'):
            raise ValueError(f"Invalid side: {self.side}")
