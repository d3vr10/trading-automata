from typing import List, Dict, Any, Type, Optional
import logging
import yaml
from pathlib import Path

from .base import BaseStrategy
from trading_bot.monitoring.event_logger import EventLogger


logger = logging.getLogger(__name__)


class StrategyRegistry:
    """Registry for available trading strategies.

    Manages strategy registration and loading from configuration.
    """

    # Registry of available strategy classes
    STRATEGIES: Dict[str, Type[BaseStrategy]] = {}

    @classmethod
    def register(cls, name: str, strategy_class: Type[BaseStrategy]) -> None:
        """Register a strategy class.

        Args:
            name: Name to register strategy under
            strategy_class: Strategy class to register
        """
        cls.STRATEGIES[name] = strategy_class
        logger.debug(f"Registered strategy: {name}")

    @classmethod
    def get(cls, name: str) -> Type[BaseStrategy]:
        """Get a registered strategy class.

        Args:
            name: Strategy class name

        Returns:
            Strategy class

        Raises:
            ValueError: If strategy not found.
        """
        if name not in cls.STRATEGIES:
            raise ValueError(f"Unknown strategy: {name}")
        return cls.STRATEGIES[name]

    @classmethod
    def load_from_config(cls, config_path: str, event_logger: Optional[EventLogger] = None) -> List[BaseStrategy]:
        """Load strategies from YAML configuration file.

        Args:
            config_path: Path to YAML config file
            event_logger: Optional event logger for strategy decision tracking

        Returns:
            List of instantiated strategy objects.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            ValueError: If configuration is invalid.
        """
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Strategy config file not found: {config_path}")

        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML config: {e}")

        strategies = []
        for strat_config in config.get('strategies', []):
            if not strat_config.get('enabled', True):
                logger.info(f"Skipping disabled strategy: {strat_config.get('name')}")
                continue

            try:
                strategy = cls._create_strategy(strat_config, event_logger)
                if strategy:
                    strategies.append(strategy)
            except Exception as e:
                logger.error(f"Failed to load strategy {strat_config.get('name')}: {e}")
                raise

        logger.info(f"Loaded {len(strategies)} strategies")
        return strategies

    @classmethod
    def _create_strategy(cls, config: Dict[str, Any], event_logger: Optional[EventLogger] = None) -> BaseStrategy:
        """Create a strategy instance from config.

        Args:
            config: Strategy configuration dictionary
            event_logger: Optional event logger for strategy decision tracking

        Returns:
            Instantiated strategy object.

        Raises:
            ValueError: If configuration is invalid.
        """
        class_name = config.get('class')
        strategy_name = config.get('name')

        if not class_name:
            raise ValueError("Strategy config missing 'class' field")
        if not strategy_name:
            raise ValueError("Strategy config missing 'name' field")

        # Get the strategy class
        try:
            strategy_class = cls.get(class_name)
        except ValueError:
            raise ValueError(f"Unknown strategy class: {class_name}")

        # Get strategy parameters
        params = config.get('parameters', {})
        params['symbols'] = config.get('symbols', [])

        # Instantiate strategy with event logger
        strategy = strategy_class(name=strategy_name, config=params, event_logger=event_logger)

        # Validate configuration
        if not strategy.validate_config():
            raise ValueError(f"Invalid configuration for strategy {strategy_name}")

        logger.info(
            f"Loaded strategy: {strategy_name} "
            f"({class_name}) for symbols {params.get('symbols', [])}"
        )
        return strategy
