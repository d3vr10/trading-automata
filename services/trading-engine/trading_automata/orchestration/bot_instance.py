"""Single trading bot instance for multi-bot orchestration.

Refactored from TradingBot to be instantiated multiple times, each scoped to:
- One broker connection
- One capital allocation (virtual fence)
- One set of strategies
- Unique bot_name for tracking in database
"""

import asyncio
import logging
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import List, Optional

from trading_automata.brokers.factory import BrokerFactory
from trading_automata.brokers.base import Environment, IBroker
from trading_automata.config.bot_config import BotConfig
from trading_automata.data.alpaca_data import AlpacaDataProvider
from trading_automata.data.models import Bar
from trading_automata.database.models import DatabaseConnection
from trading_automata.database.repository import TradeRepository
from trading_automata.database.health import HealthCheckRegistry
from trading_automata.execution.order_manager import OrderManager
from trading_automata.monitoring.event_logger import EventLogger
from trading_automata.monitoring.logger import get_logger, BotLoggerAdapter
from trading_automata.notifications.telegram_bot import BotScopedTelegram
from trading_automata.portfolio.virtual_manager import VirtualPortfolioManager
from trading_automata.strategies.base import BaseStrategy
from trading_automata.strategies.registry import StrategyRegistry
from trading_automata.metrics import (
    engine_evaluation_cycles_total,
    engine_broker_errors_total,
    engine_trades_executed_total,
)
from trading_automata.utils.exceptions import TradingBotError
from trading_automata.utils.strategy_warmer import warm_up_all_strategies


_base_logger = get_logger(__name__)


class BotInstance:
    """Single autonomous trading bot instance.

    Scoped to one broker, one capital allocation, and one set of strategies.
    Multiple instances run concurrently under BotOrchestrator.
    """

    def __init__(
        self,
        config: BotConfig,
        db: DatabaseConnection,
        trade_repo: TradeRepository,
        health_checks: HealthCheckRegistry,
        event_logger: EventLogger,
        telegram_bot: Optional[BotScopedTelegram],
        session_factory,
    ):
        """Initialize bot instance.

        Args:
            config: BotConfig for this bot
            db: Shared DatabaseConnection
            trade_repo: Shared TradeRepository
            health_checks: Shared HealthCheckRegistry
            event_logger: Shared EventLogger
            telegram_bot: BotScopedTelegram (or None if Telegram disabled)
            session_factory: async_sessionmaker for DB sessions
        """
        self.config = config
        self.bot_name = config.name

        # Create logger adapter with bot name context
        self.logger = BotLoggerAdapter(_base_logger, {'bot_name': self.bot_name})

        self.db = db
        self.trade_repo = trade_repo
        self.health_checks = health_checks
        self.event_logger = event_logger
        self.telegram_bot = telegram_bot
        self.session_factory = session_factory

        # Core trading components
        self.broker: Optional[IBroker] = None
        self.data_provider: Optional[AlpacaDataProvider] = None
        self.order_manager: Optional[OrderManager] = None
        self.portfolio_manager: Optional[VirtualPortfolioManager] = None
        self.strategies: List[BaseStrategy] = []

        # State
        self._running = False
        self._paused = False
        self.start_time = datetime.now(UTC)

        # Broker reconnection tracking
        self._broker_reconnect_attempts = 0
        self._broker_max_reconnect_attempts = 10
        self._broker_reconnect_base_delay = 5
        self._last_broker_reconnect_attempt: Optional[datetime] = None

        # Health check task
        self._health_check_task: Optional[asyncio.Task] = None
        self._last_health_check_save = datetime.now(UTC)

        # Metrics / faulty bot detection
        self._last_heartbeat = datetime.now(UTC)
        self._evaluation_count = 0
        self._consecutive_broker_errors = 0
        self._faulty = False
        self._faulty_reason: Optional[str] = None

        self.logger.info(f"Initialized")

    async def setup(self) -> bool:
        """Setup bot components.

        Initializes broker, data provider, order manager, portfolio manager,
        and loads strategies from config.

        Returns:
            True if setup successful, False otherwise
        """
        try:
            self.logger.info(f"Setting up bot components...")

            # Create broker
            self.logger.debug(f"Creating {self.config.broker.type} broker...")
            environment = Environment(self.config.broker.environment)

            # Build broker config dictionary
            broker_config = {
                'api_key': self.config.broker.api_key,
                'secret_key': self.config.broker.secret_key,
            }
            if self.config.broker.passphrase:
                broker_config['passphrase'] = self.config.broker.passphrase

            self.broker = BrokerFactory.create_broker(
                broker_type=self.config.broker.type,
                environment=environment,
                config=broker_config,
            )

            if not self.broker.connect():
                self.logger.error(f"Failed to connect to broker")
                return False

            # Create data provider
            self.logger.debug(f"Creating data provider...")
            data_api_key = self.config.data_provider.api_key or self.config.broker.api_key
            data_secret_key = self.config.data_provider.secret_key or self.config.broker.secret_key

            self.data_provider = AlpacaDataProvider(
                api_key=data_api_key,
                secret_key=data_secret_key,
            )

            # Connect data provider
            if not self.data_provider.connect():
                self.logger.error(f"Failed to connect to data provider")
                return False
            self.logger.info(f"Connected to data provider")

            # Create order manager
            self.order_manager = OrderManager(self.broker)
            self.logger.debug(f"Order manager created")

            # Create virtual portfolio manager
            self.portfolio_manager = VirtualPortfolioManager(
                broker=self.broker,
                order_manager=self.order_manager,
                allocation=self.config.allocation,
                fence=self.config.fence,
                risk=self.config.risk,
                logger=self.logger,
            )
            self.logger.info(f"Portfolio manager initialized (allocation: {self.config.allocation.amount} {self.config.allocation.type}, fence: {self.config.fence.type})")

            # Register strategies
            self.logger.debug(f"Registering built-in strategy classes...")
            self._register_strategies()

            # Load strategies from config
            self.logger.info(f"Loading strategies from {self.config.strategy_config}...")
            strategies = StrategyRegistry.load_from_config(
                config_path=self.config.strategy_config,
                event_logger=self.event_logger,
            )
            self.strategies = [s for s in strategies if s]

            if not self.strategies:
                self.logger.error(f"No strategies loaded from {self.config.strategy_config}")
                return False

            self.logger.info(f"Loaded {len(self.strategies)} strategies: {', '.join(s.name for s in self.strategies)}")

            # Register health checks
            for strategy in self.strategies:
                self.health_checks.register(
                    broker=self.config.broker.type,
                    strategy=strategy.name,
                    bot_name=self.bot_name,
                )

            # Warm up strategies
            self.logger.debug(f"Warming up strategies...")
            warm_up_all_strategies(self.strategies)

            # Log monitored symbols
            symbols = set()
            for strategy in self.strategies:
                symbols.update(strategy.config.get('symbols', []))
            if symbols:
                self.logger.info(f"Monitoring symbols: {', '.join(sorted(symbols))}")

            self.logger.info(f"✅ Setup complete")
            return True

        except Exception as e:
            self.logger.error(f"Setup failed: {e}", exc_info=True)
            return False

    async def start(self) -> None:
        """Start trading loop.

        Runs the main trading loop and handles cleanup.
        """
        if not await self.setup():
            self.logger.error(f"Setup failed, cannot start")
            return

        self._running = True
        self.logger.info(f"✅ All startup checks passed, starting trading loop...")

        try:
            # Start health check task
            self._health_check_task = asyncio.create_task(self._health_check_loop())

            await self._run_trading_loop()

        except KeyboardInterrupt:
            self.logger.info(f"Interrupted by user")
        except Exception as e:
            self.logger.error(f"Error in trading loop: {e}", exc_info=True)
        finally:
            await self._cleanup_async()
            self.stop()

    async def _health_check_loop(self) -> None:
        """Periodically save health checks to database."""
        health_check_interval = self.config.trade_frequency.poll_interval_minutes * 60

        while self._running:
            try:
                await asyncio.sleep(health_check_interval)

                if self.health_checks:
                    await self.health_checks.save_all()
                    self._last_health_check_save = datetime.now(UTC)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health check error: {e}")

    async def _run_trading_loop(self) -> None:
        """Main trading loop.

        Continuously polls for new bars and processes signals.
        """
        poll_interval = self.config.trade_frequency.poll_interval_minutes * 60
        self.logger.info(f"Trading loop started (poll interval: {poll_interval}s)")

        while self._running:
            try:
                # Try broker reconnect if disconnected
                if not await self._try_broker_reconnect():
                    self.logger.warning(f"Broker disconnected, waiting for reconnection...")
                    await asyncio.sleep(poll_interval)
                    continue

                # Get all symbols from all strategies
                symbols = set()
                for strategy in self.strategies:
                    symbols.update(strategy.config.get('symbols', []))

                # Process bars for each symbol
                for symbol in symbols:
                    try:
                        bar = self.data_provider.get_latest_bar(symbol)
                        if bar:
                            await self._process_bar(bar)
                    except Exception as e:
                        self.logger.error(f"Error processing bar for {symbol}: {e}")

                # Update metrics
                self._evaluation_count += 1
                self._last_heartbeat = datetime.now(UTC)
                self._consecutive_broker_errors = 0  # Reset on successful cycle
                engine_evaluation_cycles_total.labels(bot_name=self.bot_name).inc()

                # Update pending orders
                if self.order_manager:
                    self.order_manager.update_pending_orders()

                # Refresh portfolio
                if self.portfolio_manager:
                    self.portfolio_manager.refresh_state()

                # Sleep before next poll
                await asyncio.sleep(poll_interval)

            except Exception as e:
                self.logger.error(f"Trading loop error: {e}")
                await asyncio.sleep(poll_interval)

    async def _process_bar(self, bar: Bar) -> None:
        """Process a bar through all strategies."""
        await self.event_logger.log_bar_received(
            symbol=bar.symbol,
            strategy="",
            broker=self.config.broker.type,
            details={
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": int(bar.volume) if bar.volume else 0,
            },
            bot_name=self.bot_name,
        )

        # Get signals from all strategies
        for strategy in self.strategies:
            if bar.symbol not in strategy.config.get('symbols', []):
                continue

            try:
                signal = strategy.on_bar(bar)
                if signal:
                    await self.event_logger.log_signal_generated(
                        symbol=signal.symbol,
                        strategy=strategy.name,
                        broker=self.config.broker.type,
                        action=signal.action,
                        quantity=float(signal.quantity),
                        confidence=float(signal.confidence) if signal.confidence else 0.5,
                        details=signal.metadata or {},
                        bot_name=self.bot_name,
                    )

                    # Execute if not paused
                    if not self._paused:
                        order_id = self.portfolio_manager.execute_signal_if_valid(signal)
                        if order_id:
                            engine_trades_executed_total.labels(
                                bot_name=self.bot_name,
                                broker=self.config.broker.type,
                            ).inc()
                            await self._record_trade_entry(strategy, signal, order_id)

                            if self.telegram_bot:
                                await self.telegram_bot.send_trade_alert(
                                    symbol=signal.symbol,
                                    side=signal.action,
                                    price=bar.close,
                                    quantity=signal.quantity,
                                    strategy=strategy.name,
                                )

            except Exception as e:
                self.logger.error(
                    f"Error processing signal from {strategy.name}: {e}",
                    exc_info=True,
                )

    async def _record_trade_entry(self, strategy: BaseStrategy, signal, order_id: str) -> None:
        """Record trade entry in database."""
        try:
            trade_id = await self.trade_repo.record_trade_entry(
                symbol=signal.symbol,
                strategy=strategy.name,
                broker=self.config.broker.type,
                entry_price=Decimal(str(signal.metadata.get('price', 0))),
                entry_quantity=Decimal(str(signal.quantity or 0)),
                entry_order_id=order_id,
                bot_name=self.bot_name,
            )

            self.logger.info(f"Recorded trade entry #{trade_id} for {signal.symbol}")

        except Exception as e:
            self.logger.error(f"Failed to record trade entry: {e}")

    async def _record_trade_exit(self, strategy: BaseStrategy, signal, order_id: str) -> None:
        """Record trade exit in database."""
        try:
            # Find matching open trade
            async with self.session_factory() as session:
                open_trades = await self.trade_repo.get_trades_by_strategy(
                    strategy=strategy.name,
                    bot_name=self.bot_name,
                )

            open_trades = [t for t in open_trades if t.get('exit_order_id') is None and t['symbol'] == signal.symbol]

            if open_trades:
                trade_to_exit = open_trades[0]
                await self.trade_repo.record_trade_exit(
                    trade_id=trade_to_exit['id'],
                    exit_price=Decimal(str(signal.metadata.get('price', 0))),
                    exit_quantity=Decimal(str(signal.quantity or 0)),
                    exit_order_id=order_id,
                    bot_name=self.bot_name,
                )
                self.logger.info(f"Recorded trade exit for trade #{trade_to_exit['id']}")
            else:
                self.logger.warning(f"No open trade found to exit for {signal.symbol}")

        except Exception as e:
            self.logger.error(f"Failed to record trade exit: {e}")

    async def _record_session_start(self) -> None:
        """Record bot session start."""
        try:
            session_id = int(self.start_time.timestamp() * 1000)
            await self.trade_repo.record_session_start(
                session_id=session_id,
                started_at=self.start_time,
                bot_name=self.bot_name,
            )
        except Exception as e:
            self.logger.error(f"Failed to record session start: {e}")

    async def _try_broker_reconnect(self) -> bool:
        """Try to reconnect to broker with exponential backoff.

        Returns:
            True if connected, False otherwise
        """
        if self.broker._connected:
            return True

        # Calculate backoff delay
        delay_multiplier = min(2 ** self._broker_reconnect_attempts, 2 ** 4)
        delay = self._broker_reconnect_base_delay * delay_multiplier

        # Check if enough time has passed since last attempt
        now = datetime.now(UTC)
        if self._last_broker_reconnect_attempt:
            seconds_since = (now - self._last_broker_reconnect_attempt).total_seconds()
            if seconds_since < delay:
                return False

        # Try to reconnect
        self._last_broker_reconnect_attempt = now
        if self.broker.connect():
            self.logger.info(f"Broker reconnected successfully")
            self._broker_reconnect_attempts = 0
            return True
        else:
            self._broker_reconnect_attempts += 1
            self._consecutive_broker_errors += 1
            engine_broker_errors_total.labels(
                bot_name=self.bot_name, error_type="connection",
            ).inc()
            self.logger.warning(
                f"Broker reconnection failed "
                f"(attempt {self._broker_reconnect_attempts}/{self._broker_max_reconnect_attempts})"
            )
            return False

    async def _cleanup_async(self) -> None:
        """Cleanup async resources."""
        # Cancel health check task
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()

        # Save final health checks
        if self.health_checks:
            try:
                await self.health_checks.save_all()
            except Exception as e:
                self.logger.error(f"Failed to save final health checks: {e}")

        # Log final stats
        if self.portfolio_manager:
            stats = self.portfolio_manager.get_portfolio_stats()
            self.logger.info(f"Final portfolio stats: {stats}")

        for strategy in self.strategies:
            stats = strategy.get_stats()
            self.logger.info(f"Strategy {strategy.name} stats: {stats}")

    def stop(self) -> None:
        """Stop the bot."""
        self.logger.info(f"Stopping bot...")
        self._running = False

        if self.broker:
            self.broker.disconnect()

    def _register_strategies(self) -> None:
        """Register all available strategies."""
        from trading_automata.strategies.examples.mean_reversion import MeanReversionStrategy
        from trading_automata.strategies.examples.momentum import MomentumStrategy
        from trading_automata.strategies.examples.rsi_atr_trend import RSIATRTrendStrategy
        from trading_automata.strategies.sigma_series.sigma_fast import SigmaSeriesFastStrategy
        from trading_automata.strategies.sigma_series.sigma_alpha import SigmaSeriesAlphaStrategy
        from trading_automata.strategies.sigma_series.sigma_alpha_bull import SigmaSeriesAlphaBullStrategy

        StrategyRegistry.register('MeanReversionStrategy', MeanReversionStrategy)
        StrategyRegistry.register('MomentumStrategy', MomentumStrategy)
        StrategyRegistry.register('RSIATRTrendStrategy', RSIATRTrendStrategy)
        StrategyRegistry.register('SigmaSeriesFastStrategy', SigmaSeriesFastStrategy)
        StrategyRegistry.register('SigmaSeriesAlphaStrategy', SigmaSeriesAlphaStrategy)
        StrategyRegistry.register('SigmaSeriesAlphaBullStrategy', SigmaSeriesAlphaBullStrategy)

    def _set_paused(self, paused: bool) -> None:
        """Set pause state."""
        self._paused = paused
        self.logger.info(f"Trading {'paused' if paused else 'resumed'}")

    # ── Faulty bot detection ──────────────────────────

    HEARTBEAT_TIMEOUT_FACTOR = 2  # faulty if no heartbeat for > 2x poll interval
    CONSECUTIVE_ERROR_THRESHOLD = 5

    @property
    def is_faulty(self) -> bool:
        """Check all faulty conditions and return current faulty state."""
        self._check_faulty()
        return self._faulty

    def _check_faulty(self) -> None:
        """Evaluate faulty conditions.

        A bot is marked faulty when any of:
        1. Heartbeat timeout — no heartbeat for > 2x expected interval
        2. Consecutive broker errors — 5+ failed broker API calls in a row
        3. Unrecovered exception — bot stopped unexpectedly (not user-initiated)
        """
        if not self._running:
            self._faulty = False
            self._faulty_reason = None
            return

        now = datetime.now(UTC)
        poll_interval_s = self.config.trade_frequency.poll_interval_minutes * 60
        heartbeat_timeout = poll_interval_s * self.HEARTBEAT_TIMEOUT_FACTOR

        # Condition 1: Heartbeat timeout
        age = (now - self._last_heartbeat).total_seconds()
        if age > heartbeat_timeout and self._evaluation_count > 0:
            self._faulty = True
            self._faulty_reason = f"heartbeat_stale ({age:.0f}s > {heartbeat_timeout:.0f}s)"
            return

        # Condition 2: Consecutive broker errors
        if self._consecutive_broker_errors >= self.CONSECUTIVE_ERROR_THRESHOLD:
            self._faulty = True
            self._faulty_reason = f"consecutive_broker_errors ({self._consecutive_broker_errors})"
            return

        self._faulty = False
        self._faulty_reason = None
