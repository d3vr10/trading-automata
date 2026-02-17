import asyncio
import logging
import sys
from typing import List, Optional
from decimal import Decimal
from datetime import datetime, time, UTC

import psycopg

from config.settings import load_settings
from trading_bot.brokers.factory import BrokerFactory
from trading_bot.brokers.base import Environment
from trading_bot.data.alpaca_data import AlpacaDataProvider
from trading_bot.data.models import Bar
from trading_bot.strategies.registry import StrategyRegistry
from trading_bot.strategies.base import BaseStrategy
from trading_bot.portfolio.manager import PortfolioManager
from trading_bot.execution.order_manager import OrderManager
from trading_bot.monitoring.logger import setup_logging, get_logger
from trading_bot.monitoring.event_logger import init_event_logger, get_event_logger
from trading_bot.utils.exceptions import TradingBotError
from trading_bot.utils.strategy_warmer import warm_up_all_strategies
from trading_bot.database.repository import TradeRepository
from trading_bot.database.health import HealthCheckRegistry
from trading_bot.notifications.telegram_bot import TradingBotTelegram


logger = get_logger(__name__)


class TradingBot:
    """Main trading bot orchestrator.

    Coordinates all components including broker, data provider,
    strategies, order execution, and portfolio management.
    """

    def __init__(self):
        """Initialize trading bot."""
        self.settings = None
        self.broker = None
        self.data_provider = None
        self.order_manager = None
        self.portfolio_manager = None
        self.strategies = []
        self._running = False

        # Session tracking - records when this bot process started
        self.start_time = datetime.now(UTC)

        # Database components
        self.db_conn: Optional[psycopg.AsyncConnection] = None
        self.trade_repo: Optional[TradeRepository] = None
        self.health_checks: Optional[HealthCheckRegistry] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._last_health_check_save = datetime.now(UTC)

        # Event logging
        self.event_logger = None

        # Notification components
        self.telegram_bot: Optional[TradingBotTelegram] = None

        # Broker reconnection tracking
        self._broker_reconnect_attempts = 0
        self._broker_max_reconnect_attempts = 10
        self._broker_reconnect_base_delay = 5  # seconds
        self._last_broker_reconnect_attempt: Optional[datetime] = None

    async def setup(self) -> bool:
        """Setup trading bot components.

        Initializes all bot components. If optional components fail (Telegram, Database, Broker),
        setup continues with degraded functionality. The trading loop will retry broker
        reconnection with exponential backoff.

        Returns:
            True if core setup successful, False if unable to initialize strategies.
        """
        try:
            # Load settings
            logger.info("Loading configuration...")
            self.settings = load_settings()

            # Setup logging
            setup_logging(
                level=self.settings.log_level,
                log_file=self.settings.log_file
            )

            logger.info(
                f"Trading Bot initialized - Environment: {self.settings.trading_environment.upper()}"
            )

            # Create broker
            logger.info(f"Creating {self.settings.broker} broker...")
            environment = Environment(self.settings.trading_environment)

            # Build broker config based on broker type
            broker_config = self._build_broker_config()

            self.broker = BrokerFactory.create_broker(
                broker_type=self.settings.broker,
                environment=environment,
                config=broker_config
            )

            # Try to connect to broker (will retry in main loop if it fails)
            if not self.broker.connect():
                logger.error(
                    f"Failed to connect to {self.settings.broker} broker. "
                    "Bot will retry in main loop. Check credentials and API key."
                )
                # Continue setup - trading will wait until broker is connected
            else:
                try:
                    account = self.broker.get_account()
                    logger.info(
                        f"Connected to broker. Account: {account['account_id']}, "
                        f"Portfolio Value: ${account['portfolio_value']:.2f}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to fetch account info: {e}. "
                        "Bot will retry in main loop."
                    )

            # Create data provider
            logger.info("Initializing data provider...")

            # Use Alpaca data provider for now (works for stocks, options, crypto)
            # In future, could add Coinbase data provider for crypto
            self.data_provider = AlpacaDataProvider(
                api_key=self.settings.alpaca_api_key,
                secret_key=self.settings.alpaca_secret_key,
            )
            if not self.data_provider.connect():
                logger.error("Failed to connect to data provider")
                return False

            # Create order manager
            self.order_manager = OrderManager(self.broker)

            # Create portfolio manager
            self.portfolio_manager = PortfolioManager(
                broker=self.broker,
                order_manager=self.order_manager,
                max_position_size=Decimal(str(self.settings.max_position_size)),
                max_portfolio_risk=Decimal(str(self.settings.max_portfolio_risk)),
            )

            # Initialize database connection (async)
            logger.info("Connecting to database...")
            try:
                self.db_conn = await psycopg.AsyncConnection.connect(
                    self.settings.database_url
                )
                self.trade_repo = TradeRepository(self.db_conn)
                self.health_checks = HealthCheckRegistry(self.db_conn)
                logger.info("✅ Connected to PostgreSQL database")

                # Initialize event logger for decision tracking
                self.event_logger = init_event_logger(self.settings.database_url)
                logger.info("✅ Event logger initialized")

                # Record session start time
                await self._record_session_start()
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                logger.warning("Continuing without database - trade history will not be recorded")
                self.db_conn = None
                self.trade_repo = None
                self.health_checks = None
                self.event_logger = None

            # Initialize Telegram bot
            logger.info("Initializing Telegram bot...")
            self.telegram_bot = TradingBotTelegram(
                self.settings.telegram_token,
                self.settings.telegram_chat_id,
                database_url=self.settings.database_url
            )
            telegram_ready = await self.telegram_bot.initialize()
            if telegram_ready:
                logger.info("✅ Telegram bot initialized")
                await self.telegram_bot.send_message(
                    "🤖 <b>Trading Bot Started</b>\n"
                    f"Environment: {self.settings.trading_environment.upper()}\n"
                    f"Broker: {self.settings.broker.upper()}"
                )
            else:
                logger.warning("Telegram bot not configured - notifications disabled")

            # Register strategies
            logger.info("Registering strategies...")
            self._register_strategies()

            # Load strategies from config
            logger.info(f"Loading strategies from {self.settings.strategy_config_path}...")
            self.strategies = StrategyRegistry.load_from_config(
                self.settings.strategy_config_path,
                event_logger=self.event_logger
            )

            if not self.strategies:
                logger.error("No strategies configured")
                return False

            logger.info(f"Loaded {len(self.strategies)} active strategies")
            for strategy in self.strategies:
                logger.info(f"  - {strategy.name}: {strategy.config.get('symbols', [])}")

            # Register health checks for each strategy
            if self.health_checks:
                for strategy in self.strategies:
                    self.health_checks.register(self.settings.broker, strategy.name)
                logger.info(f"Registered {len(self.strategies)} health checks")

            # Warm up strategies with historical data (load indicators immediately)
            logger.info("Warming up strategies with historical data...")
            try:
                warm_up_all_strategies(
                    self.strategies,
                    num_bars=100,
                    use_cache=self.settings.use_cached_data
                )
            except Exception as e:
                logger.warning(f"Strategy warm-up failed: {e}. Bot will wait for live data instead.")

            return True

        except TradingBotError as e:
            logger.error(f"Trading bot error during setup: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during setup: {e}")
            return False

    def _build_broker_config(self) -> dict:
        """Build broker configuration based on selected broker type.

        Returns:
            Dictionary with broker-specific credentials and config.

        Raises:
            ValueError: If required credentials are missing for selected broker.
        """
        broker_type = self.settings.broker.lower()

        if broker_type == 'alpaca':
            if not self.settings.alpaca_api_key or not self.settings.alpaca_secret_key:
                raise ValueError(
                    "Alpaca broker requires ALPACA_API_KEY and ALPACA_SECRET_KEY"
                )
            return {
                'api_key': self.settings.alpaca_api_key,
                'secret_key': self.settings.alpaca_secret_key,
            }

        elif broker_type == 'coinbase':
            if (not self.settings.coinbase_api_key or
                not self.settings.coinbase_secret_key or
                not self.settings.coinbase_passphrase):
                raise ValueError(
                    "Coinbase broker requires COINBASE_API_KEY, COINBASE_SECRET_KEY, and COINBASE_PASSPHRASE"
                )
            return {
                'api_key': self.settings.coinbase_api_key,
                'secret_key': self.settings.coinbase_secret_key,
                'passphrase': self.settings.coinbase_passphrase,
            }

        else:
            raise ValueError(
                f"Unsupported broker: {broker_type}. Supported: alpaca, coinbase"
            )

    def _register_strategies(self) -> None:
        """Register all available strategy classes."""
        from trading_bot.strategies.examples.buy_and_hold import BuyAndHoldStrategy
        from trading_bot.strategies.examples.mean_reversion import MeanReversionStrategy
        from trading_bot.strategies.examples.momentum import MomentumStrategy
        from trading_bot.strategies.examples.rsi_atr_trend import RSIATRTrendStrategy

        StrategyRegistry.register('BuyAndHoldStrategy', BuyAndHoldStrategy)
        StrategyRegistry.register('MeanReversionStrategy', MeanReversionStrategy)
        StrategyRegistry.register('MomentumStrategy', MomentumStrategy)
        StrategyRegistry.register('RSIATRTrendStrategy', RSIATRTrendStrategy)

    async def _record_session_start(self) -> None:
        """Record the current bot session start time to database.

        This allows the CLI to calculate actual bot process uptime
        rather than database lifetime. Called after database is initialized.
        """
        if not self.db_conn:
            return

        try:
            # Record session start in bot_sessions table
            query = """
                INSERT INTO bot_sessions (session_id, started_at)
                VALUES (%s, %s)
            """
            session_id = self.start_time.timestamp()  # Use timestamp as unique session ID
            async with self.db_conn.cursor() as cur:
                await cur.execute(query, (session_id, self.start_time))
            logger.debug(f"Session started at {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        except Exception as e:
            logger.warning(f"Failed to record session start: {e}")

    def _get_all_symbols(self) -> List[str]:
        """Get all symbols from all strategies.

        Returns:
            List of unique symbols.
        """
        symbols = set()
        for strategy in self.strategies:
            symbols.update(strategy.config.get('symbols', []))
        return sorted(list(symbols))

    async def start(self) -> None:
        """Start the trading bot.

        Connects to data feeds and runs the main trading loop.
        """
        if not await self.setup():
            logger.error("Failed to setup trading bot")
            return

        self._running = True

        try:
            await self._run_trading_loop()
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Error in trading loop: {e}")
        finally:
            await self._cleanup_async()
            self.stop()

    async def _try_broker_reconnect(self) -> bool:
        """Try to reconnect to broker with exponential backoff.

        Returns:
            True if connected, False otherwise.
        """
        if self.broker._connected:
            return True

        # Calculate delay with exponential backoff
        delay_multiplier = min(2 ** self._broker_reconnect_attempts, 2 ** 4)  # Max 16x
        delay = self._broker_reconnect_base_delay * delay_multiplier

        # Check if we should retry (don't retry more frequently than the calculated delay)
        now = datetime.now(UTC)
        if self._last_broker_reconnect_attempt:
            seconds_since_attempt = (now - self._last_broker_reconnect_attempt).total_seconds()
            if seconds_since_attempt < delay:
                return False

        # Try to reconnect
        self._last_broker_reconnect_attempt = now
        if self.broker.connect():
            logger.info("✅ Broker reconnected successfully")
            self._broker_reconnect_attempts = 0
            return True
        else:
            self._broker_reconnect_attempts += 1
            next_delay = self._broker_reconnect_base_delay * min(2 ** self._broker_reconnect_attempts, 2 ** 4)
            logger.warning(
                f"Broker reconnection failed (attempt {self._broker_reconnect_attempts}/"
                f"{self._broker_max_reconnect_attempts}). Next retry in {next_delay}s"
            )

            if self._broker_reconnect_attempts >= self._broker_max_reconnect_attempts:
                logger.error(
                    f"Max broker reconnection attempts ({self._broker_max_reconnect_attempts}) "
                    "reached. Waiting for manual intervention or API restoration."
                )
            return False

    async def _run_trading_loop(self) -> None:
        """Run the main trading loop.

        Processes bar data and executes trading signals.
        Handles broker disconnections gracefully with automatic retry.
        """
        logger.info("Starting trading loop...")

        symbols = self._get_all_symbols()
        logger.info(f"Monitoring symbols: {symbols}")

        # Start health check monitoring task
        if self.health_checks:
            self._health_check_task = asyncio.create_task(self._monitor_health_checks())

        # For now, we'll fetch the latest bar for each symbol periodically
        # In a production system, you'd use websockets for real-time data
        while self._running:
            try:
                # Check broker connection and try to reconnect if needed
                if not self.broker._connected:
                    broker_connected = await self._try_broker_reconnect()
                    if not broker_connected:
                        logger.info("Broker not connected - waiting before next reconnection attempt")
                        await asyncio.sleep(10)
                        continue

                # Fetch latest bars
                for symbol in symbols:
                    try:
                        bar = self.data_provider.get_latest_bar(symbol)
                        if bar:
                            await self._process_bar(bar)
                    except Exception as e:
                        logger.warning(f"Error getting bar for {symbol}: {e}")
                        # Record connection error to health checks
                        if self.health_checks:
                            for strategy in self.strategies:
                                check = self.health_checks.get(
                                    self.settings.broker, strategy.name
                                )
                                if check:
                                    await check.record_connection_error(str(e))

                # Update pending orders
                self.order_manager.update_pending_orders()

                # Refresh portfolio state
                self.portfolio_manager.refresh_state()

                # Periodically save health checks (configurable interval, default 5 minutes)
                if self.health_checks and (
                    datetime.now(UTC) - self._last_health_check_save
                ).total_seconds() >= self.settings.health_check_interval:
                    await self.health_checks.save_all()
                    self._last_health_check_save = datetime.now(UTC)

                # Sleep to avoid overwhelming the API
                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(60)

    async def _process_bar(self, bar: Bar) -> None:
        """Process a bar and execute any resulting signals.

        Args:
            bar: Bar data to process
        """
        # Log bar received to event logger
        if self.event_logger:
            self.event_logger.log_bar_received(
                symbol=bar.symbol,
                strategy="all",
                broker=self.settings.broker,
                details={
                    "open": str(bar.open),
                    "high": str(bar.high),
                    "low": str(bar.low),
                    "close": str(bar.close),
                    "volume": bar.volume,
                    "timestamp": bar.timestamp.isoformat() if hasattr(bar.timestamp, 'isoformat') else str(bar.timestamp),
                }
            )

        # Record bar received in health checks
        if self.health_checks:
            for strategy in self.strategies:
                if bar.symbol in strategy.config.get('symbols', []):
                    check = self.health_checks.get(self.settings.broker, strategy.name)
                    if check:
                        await check.record_bar_received()

        # Get signals from all strategies for this symbol
        signals = []
        for strategy in self.strategies:
            if bar.symbol not in strategy.config.get('symbols', []):
                continue

            try:
                signal = strategy.on_bar(bar)
                if signal:
                    signals.append((strategy, signal))
                    # Log signal to event logger
                    if self.event_logger:
                        self.event_logger.log_signal_generated(
                            symbol=signal.symbol,
                            strategy=strategy.name,
                            broker=self.settings.broker,
                            action=signal.action,
                            quantity=float(signal.quantity) if signal.quantity else 0,
                            confidence=signal.confidence,
                            details=signal.metadata or {}
                        )
            except Exception as e:
                logger.error(f"Error in strategy {strategy.name}: {e}")

        # Execute signals
        for strategy, signal in signals:
            logger.info(f"[{signal.symbol}] [{strategy.name}] Generated signal: {signal}")

            # Try to execute the signal
            order_id = self.portfolio_manager.execute_signal_if_valid(signal)
            if order_id:
                logger.info(f"[{signal.symbol}] [{strategy.name}] Signal executed as order {order_id}")

                # Record order to database
                if self.trade_repo:
                    try:
                        await self._record_trade_entry(strategy, signal, order_id)
                    except Exception as e:
                        logger.error(f"Failed to record trade entry: {e}")

                # Send Telegram alert
                if self.telegram_bot:
                    try:
                        # Get current price from metadata if available
                        current_price = signal.metadata.get('price') if signal.metadata else None
                        await self.telegram_bot.send_trade_alert(
                            symbol=signal.symbol,
                            side=signal.action,
                            price=Decimal(str(current_price)) if current_price else Decimal("0"),
                            quantity=signal.quantity,
                            strategy=strategy.name
                        )
                    except Exception as e:
                        logger.error(f"Failed to send Telegram alert: {e}")

                # Record order in health checks
                if self.health_checks:
                    check = self.health_checks.get(self.settings.broker, strategy.name)
                    if check:
                        await check.record_order_submitted()

            else:
                logger.info(f"[{signal.symbol}] [{strategy.name}] Signal not executed (validation failed or no action)")

    async def _record_trade_entry(
        self, strategy: BaseStrategy, signal, order_id: str
    ) -> None:
        """Record a trade entry to the database.

        Args:
            strategy: The strategy that generated the signal
            signal: The trading signal
            order_id: The order ID from the broker
        """
        try:
            # Get current price from metadata if available
            current_price = signal.metadata.get('price') if signal.metadata else None
            trade_id = await self.trade_repo.record_trade_entry(
                symbol=signal.symbol,
                strategy=strategy.name,
                broker=self.settings.broker,
                entry_price=Decimal(str(current_price)) if current_price else Decimal("0"),
                entry_quantity=signal.quantity,
                entry_order_id=order_id,
                notes=f"Signal from {strategy.name}: {signal.action}"
            )
            logger.info(f"Recorded trade entry #{trade_id} for {signal.symbol}")
        except Exception as e:
            logger.error(f"Failed to record trade entry: {e}")

    async def _monitor_health_checks(self) -> None:
        """Monitor health checks and log status periodically."""
        while self._running:
            try:
                # Log health status every 10 minutes
                await asyncio.sleep(600)

                if self.health_checks:
                    self.health_checks.log_all_status()

                    # Check for unhealthy conditions
                    unhealthy = self.health_checks.get_unhealthy_checks()
                    if unhealthy:
                        logger.error(
                            f"⚠️  {len(unhealthy)} unhealthy checks - "
                            "consider manual intervention"
                        )

                    stale = self.health_checks.get_stale_checks()
                    if stale:
                        logger.warning(
                            f"⚠️  {len(stale)} checks with stale data - "
                            "may indicate connection issues"
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check monitoring: {e}")
                await asyncio.sleep(60)

    async def _cleanup_async(self) -> None:
        """Async cleanup of database resources."""
        # Save final health checks
        if self.health_checks:
            try:
                await self.health_checks.save_all()
                logger.info("Final health checks saved")
            except Exception as e:
                logger.error(f"Failed to save final health checks: {e}")

        # Close database connection
        if self.db_conn:
            try:
                await self.db_conn.aclose()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")

        # Stop Telegram bot
        if self.telegram_bot:
            try:
                await self.telegram_bot.send_message(
                    "🛑 <b>Trading Bot Stopped</b>\n"
                    f"Shutdown time: {datetime.now(UTC).strftime('%H:%M:%S UTC')}"
                )
                await self.telegram_bot.stop()
                logger.info("Telegram bot stopped")
            except Exception as e:
                logger.error(f"Error stopping Telegram bot: {e}")

    def stop(self) -> None:
        """Stop the trading bot and cleanup resources."""
        logger.info("Stopping trading bot...")
        self._running = False

        # Cancel health check task
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()

        # Log final stats
        if self.order_manager:
            stats = self.order_manager.get_stats()
            logger.info(f"Order stats: {stats}")

        if self.portfolio_manager:
            stats = self.portfolio_manager.get_portfolio_stats()
            logger.info(f"Portfolio stats: {stats}")

        for strategy in self.strategies:
            stats = strategy.get_stats()
            logger.info(f"Strategy {strategy.name} stats: {stats}")

        # Disconnect
        if self.data_provider:
            self.data_provider.disconnect()
        if self.broker:
            self.broker.disconnect()

        logger.info("Trading bot stopped")


def main():
    """Main entry point."""
    bot = TradingBot()
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        bot.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
