"""Sigma Series high-performance trading strategies.

Three strategies with target win rates:
- SigmaSeriesFastStrategy: 93-94% win rate, high volume momentum
- SigmaSeriesAlphaStrategy: Conservative mean-reversion, steady growth
- SigmaSeriesAlphaBullStrategy: 96.25% in bull markets, long-only trend following

All strategies use pure Python indicator calculations (no extra dependencies).
"""

from trading_automata.strategies.sigma_series.sigma_fast import SigmaSeriesFastStrategy
from trading_automata.strategies.sigma_series.sigma_alpha import SigmaSeriesAlphaStrategy
from trading_automata.strategies.sigma_series.sigma_alpha_bull import SigmaSeriesAlphaBullStrategy
from trading_automata.strategies.sigma_series.sigma_alpha_bull_crypto import SigmaSeriesAlphaBullCryptoStrategy

__all__ = [
    'SigmaSeriesFastStrategy',
    'SigmaSeriesAlphaStrategy',
    'SigmaSeriesAlphaBullStrategy',
    'SigmaSeriesAlphaBullCryptoStrategy',
]
