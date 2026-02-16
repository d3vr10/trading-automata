from typing import Dict, Any
import logging

from .base import IBroker, Environment
from .alpaca_broker import AlpacaBroker
from .coinbase_broker import CoinbaseBroker


logger = logging.getLogger(__name__)


class BrokerFactory:
    """Factory for creating broker instances.

    This factory enables easy switching between different broker implementations
    and trading environments without changing client code.

    Supported brokers:
    - alpaca: Stocks, forex, options, crypto (paper & live)
    - coinbase: Crypto only (live trading)
    """

    @staticmethod
    def create_broker(
        broker_type: str,
        environment: Environment,
        config: Dict[str, Any]
    ) -> IBroker:
        """Create a broker instance.

        Args:
            broker_type: Type of broker ('alpaca', 'coinbase', etc.)
            environment: Trading environment (PAPER or LIVE)
            config: Configuration dictionary with broker-specific parameters

        Returns:
            IBroker implementation instance.

        Raises:
            ValueError: If broker type is unsupported or config is invalid.
        """
        broker_type = broker_type.lower()

        if broker_type == 'alpaca':
            if 'api_key' not in config or 'secret_key' not in config:
                raise ValueError("Alpaca broker requires 'api_key' and 'secret_key' in config")
            logger.info(f"Creating Alpaca broker ({environment.value} mode)")
            return AlpacaBroker(
                api_key=config['api_key'],
                secret_key=config['secret_key'],
                environment=environment
            )

        elif broker_type == 'coinbase':
            if 'api_key' not in config or 'secret_key' not in config or 'passphrase' not in config:
                raise ValueError(
                    "Coinbase broker requires 'api_key', 'secret_key', and 'passphrase' in config"
                )
            logger.info(f"Creating Coinbase broker ({environment.value} mode)")
            return CoinbaseBroker(
                api_key=config['api_key'],
                secret_key=config['secret_key'],
                passphrase=config['passphrase'],
                environment=environment
            )

        else:
            raise ValueError(
                f"Unsupported broker type: {broker_type}. "
                f"Supported: alpaca, coinbase"
            )
