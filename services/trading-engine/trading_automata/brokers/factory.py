from typing import Dict, Any, TYPE_CHECKING
import logging

from .base import IBroker, Environment
from .alpaca_broker import AlpacaBroker
from .coinbase_broker import CoinbaseBroker
from .rate_limiter import RateLimitedBroker

if TYPE_CHECKING:
    from config.settings import Settings

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
    def build_config_from_settings(settings: "Settings") -> Dict[str, str]:
        """Build broker configuration dictionary from Settings object.

        Args:
            settings: Settings object with broker credentials

        Returns:
            Dictionary with broker-specific credentials and config.

        Raises:
            ValueError: If required credentials are missing for selected broker.
        """
        broker_type = settings.broker.lower()

        if broker_type == 'alpaca':
            if not settings.alpaca_api_key or not settings.alpaca_secret_key:
                raise ValueError(
                    "Alpaca broker requires ALPACA_API_KEY and ALPACA_SECRET_KEY"
                )
            return {
                'api_key': settings.alpaca_api_key,
                'secret_key': settings.alpaca_secret_key,
            }

        elif broker_type == 'coinbase':
            if (not settings.coinbase_api_key or
                not settings.coinbase_secret_key or
                not settings.coinbase_passphrase):
                raise ValueError(
                    "Coinbase broker requires COINBASE_API_KEY, COINBASE_SECRET_KEY, and COINBASE_PASSPHRASE"
                )
            return {
                'api_key': settings.coinbase_api_key,
                'secret_key': settings.coinbase_secret_key,
                'passphrase': settings.coinbase_passphrase,
            }

        else:
            raise ValueError(
                f"Unsupported broker: {broker_type}. Supported: alpaca, coinbase"
            )

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
            broker = AlpacaBroker(
                api_key=config['api_key'],
                secret_key=config['secret_key'],
                environment=environment
            )
            return RateLimitedBroker(broker, max_retries=3, base_delay=1.0)

        elif broker_type == 'coinbase':
            if 'api_key' not in config or 'secret_key' not in config or 'passphrase' not in config:
                raise ValueError(
                    "Coinbase broker requires 'api_key', 'secret_key', and 'passphrase' in config"
                )
            logger.info(f"Creating Coinbase broker ({environment.value} mode)")
            broker = CoinbaseBroker(
                api_key=config['api_key'],
                secret_key=config['secret_key'],
                passphrase=config['passphrase'],
                environment=environment
            )
            return RateLimitedBroker(broker, max_retries=3, base_delay=1.0)

        else:
            raise ValueError(
                f"Unsupported broker type: {broker_type}. "
                f"Supported: alpaca, coinbase"
            )
