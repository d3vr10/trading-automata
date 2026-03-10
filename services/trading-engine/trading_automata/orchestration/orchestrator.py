"""Multi-bot orchestrator for concurrent bot management.

Owns shared infrastructure (database, Telegram) and coordinates lifecycle
for all BotInstance objects.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
from aiohttp.web import AppRunner

from trading_automata.commands.listener import CommandListener
from trading_automata.commands.publisher import EventPublisher
from trading_automata.health_api import start_health_server
from trading_automata.metrics import engine_bots_total, engine_heartbeat_age_seconds
from trading_automata.config.loader import load_bot_configs
from trading_automata.config.bot_config import OrchestratorConfig
from trading_automata.database.models import DatabaseConnection
from trading_automata.database.repository import TradeRepository
from trading_automata.database.health import HealthCheckRegistry
from trading_automata.monitoring.event_logger import init_event_logger, get_event_logger
from trading_automata.monitoring.logger import get_logger
from trading_automata.notifications.telegram_bot import TradingBotTelegram, BotScopedTelegram
from trading_automata.orchestration.bot_instance import BotInstance


logger = get_logger(__name__)


class BotOrchestrator:
    """Orchestrates multiple BotInstance objects with shared infrastructure."""

    def __init__(self):
        """Initialize orchestrator."""
        self.orchestrator_config: Optional[OrchestratorConfig] = None
        self.db: Optional[DatabaseConnection] = None
        self.trade_repo: Optional[TradeRepository] = None
        self.health_checks: Optional[HealthCheckRegistry] = None
        self.event_logger = None
        self.telegram_bot: Optional[TradingBotTelegram] = None
        self.bot_instances: List[BotInstance] = []
        self.bot_registry: Dict[str, BotInstance] = {}  # For Telegram/API commands
        self._tasks: List[asyncio.Task] = []
        self._running = False

        # Redis inter-service communication
        self._redis: Optional[aioredis.Redis] = None
        self._event_publisher: Optional[EventPublisher] = None
        self._command_listener: Optional[CommandListener] = None

        # Health API server
        self._health_runner: Optional[AppRunner] = None

        logger.info("BotOrchestrator initialized")

    async def setup(self) -> bool:
        """Setup shared infrastructure and bot instances.

        Returns:
            True if at least one bot initialized, False otherwise
        """
        try:
            logger.info("Setting up BotOrchestrator...")

            # Load configuration
            logger.debug("Loading bot configurations...")
            self.orchestrator_config = load_bot_configs()

            global_cfg = self.orchestrator_config.global_config

            # Setup shared database
            logger.info("Setting up database...")
            self.db = DatabaseConnection(
                database_url=global_cfg.database_url,
                pool_size=global_cfg.database_pool_size,
                max_overflow=global_cfg.database_max_overflow,
            )

            # Setup shared repository
            self.trade_repo = TradeRepository(self.db.session_factory)

            # Setup shared health checks
            self.health_checks = HealthCheckRegistry(self.db.session_factory)

            # Setup shared event logger
            logger.debug("Setting up event logger...")
            init_event_logger(self.db.session_factory)
            self.event_logger = get_event_logger()

            # Setup Redis for inter-service communication (optional)
            redis_url = os.getenv("REDIS_URL", "")
            if redis_url:
                try:
                    logger.info("Connecting to Redis...")
                    self._redis = aioredis.from_url(
                        redis_url, decode_responses=True,
                        socket_connect_timeout=5,
                    )
                    await self._redis.ping()
                    self._event_publisher = EventPublisher(self._redis)
                    self._command_listener = CommandListener(self._redis, self._event_publisher)
                    self._register_command_handlers()
                    logger.info("Redis connected — inter-service communication enabled")
                except Exception as e:
                    logger.warning(f"Redis connection failed, running in standalone mode: {e}")
                    self._redis = None
                    self._event_publisher = None
                    self._command_listener = None
            else:
                logger.info("No REDIS_URL configured — running in standalone mode")

            # Setup shared Telegram bot (if configured)
            if global_cfg.telegram_token:
                logger.info("Setting up Telegram bot...")
                self.telegram_bot = TradingBotTelegram(
                    token=global_cfg.telegram_token,
                    chat_id=global_cfg.telegram_chat_id.split(',') if global_cfg.telegram_chat_id else [],
                    username_whitelist=global_cfg.telegram_username_whitelist,
                    webhook_url=global_cfg.telegram_webhook_url,
                    webhook_secret=global_cfg.telegram_webhook_secret,
                    webhook_port=global_cfg.telegram_webhook_port,
                    database_url=global_cfg.database_url,
                )
                # Register bot instances for multi-bot commands (/bots, /pause_bot, /resume_bot)
                self.telegram_bot.set_bot_registry(self.bot_registry)
            else:
                logger.warning("Telegram bot not configured (no token)")

            # Setup bot instances
            num_enabled_bots = sum(1 for b in self.orchestrator_config.bots if b.enabled)
            logger.info(f"Setting up {num_enabled_bots}/{len(self.orchestrator_config.bots)} bot instance(s)...")
            successful_bots = 0

            for bot_cfg in self.orchestrator_config.bots:
                if not bot_cfg.enabled:
                    logger.debug(f"Bot '{bot_cfg.name}' is disabled, skipping")
                    continue

                logger.info(f"Initializing bot '{bot_cfg.name}' ({bot_cfg.broker.type} {bot_cfg.broker.environment})")
                try:
                    # Create bot-scoped Telegram if shared Telegram exists
                    bot_telegram = None
                    if self.telegram_bot:
                        bot_telegram = BotScopedTelegram(self.telegram_bot, bot_cfg.name)

                    # Create bot instance
                    bot_instance = BotInstance(
                        config=bot_cfg,
                        db=self.db,
                        trade_repo=self.trade_repo,
                        health_checks=self.health_checks,
                        event_logger=self.event_logger,
                        telegram_bot=bot_telegram,
                        session_factory=self.db.session_factory,
                    )

                    # Setup bot
                    if await bot_instance.setup():
                        self.bot_instances.append(bot_instance)
                        self.bot_registry[bot_cfg.name] = bot_instance
                        successful_bots += 1
                        logger.info(f"Bot '{bot_cfg.name}' setup successfully")
                    else:
                        logger.error(f"Bot '{bot_cfg.name}' setup failed")

                except Exception as e:
                    logger.error(f"Failed to setup bot '{bot_cfg.name}': {e}", exc_info=True)

            if successful_bots == 0 and not self._command_listener:
                logger.error("No bots initialized and no Redis for API-driven commands — cannot start")
                return False

            if successful_bots > 0:
                bot_names = ', '.join(self.bot_registry.keys())
                logger.info(f"✅ Orchestrator setup complete: {successful_bots} bot(s) ready [{bot_names}]")
            else:
                logger.info("✅ Orchestrator setup complete: 0 bots — waiting for API commands via Redis")
            return True

        except Exception as e:
            logger.error(f"Orchestrator setup failed: {e}", exc_info=True)
            return False

    async def start(self) -> None:
        """Start all bot instances and shared services.

        Runs the orchestrator main loop until interrupted.
        """
        if not await self.setup():
            logger.error("Setup failed, cannot start orchestrator")
            return

        self._running = True

        try:
            # Start health API server
            health_port = int(os.getenv("HEALTH_PORT", "8081"))
            try:
                self._health_runner = await start_health_server(self, port=health_port)
            except Exception as e:
                logger.warning(f"Failed to start health API: {e}")

            # Start Redis command listener (if connected)
            if self._command_listener:
                logger.info("Starting Redis command listener...")
                redis_task = asyncio.create_task(self._command_listener.start())
                self._tasks.append(redis_task)

            # Start Telegram bot polling in background (if configured)
            telegram_task = None
            if self.telegram_bot:
                logger.info("Starting Telegram bot...")
                telegram_task = asyncio.create_task(self.telegram_bot.start())
                self._tasks.append(telegram_task)

            # Start all bot instances in parallel
            logger.info(f"Starting {len(self.bot_instances)} bot instance(s)...")
            for bot_instance in self.bot_instances:
                logger.info(f"  ▶️  Starting bot '{bot_instance.bot_name}'")
                task = asyncio.create_task(bot_instance.start())
                self._tasks.append(task)

            # Publish engine heartbeat to Redis
            if self._redis:
                await self._redis.set("engine:heartbeat", "ok", ex=30)
                logger.info("Engine heartbeat published to Redis")

            # Start metrics update loop (also refreshes heartbeat)
            metrics_task = asyncio.create_task(self._metrics_loop())
            self._tasks.append(metrics_task)

            # Wait for all tasks
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)

        except KeyboardInterrupt:
            logger.info("Orchestrator interrupted by user")
        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)
        finally:
            await self._cleanup_async()

    async def _cleanup_async(self) -> None:
        """Cleanup all resources."""
        logger.info("Cleaning up orchestrator...")

        # Stop all bot instances
        for bot_instance in self.bot_instances:
            try:
                bot_instance.stop()
            except Exception as e:
                logger.error(f"Error stopping bot '{bot_instance.bot_name}': {e}")

        # Send shutdown notifications to Telegram
        if self.telegram_bot:
            try:
                shutdown_msg = (
                    "🛑 <b>Trading Bot Cluster Stopped</b>\n"
                    f"Shutdown time: {__import__('datetime').datetime.now(__import__('datetime').UTC).strftime('%H:%M:%S UTC')}"
                )
                await self.telegram_bot.send_message(shutdown_msg)
                logger.info("Shutdown notification sent to Telegram")
            except Exception as e:
                logger.warning(f"Failed to send Telegram shutdown notification: {e}")

            # Stop Telegram bot
            try:
                await asyncio.wait_for(self.telegram_bot.stop(), timeout=3.0)
                logger.info("Telegram bot stopped")
            except asyncio.TimeoutError:
                logger.warning("Telegram bot stop timed out")
            except Exception as e:
                logger.warning(f"Error stopping Telegram bot: {e}")

        # Stop Redis command listener
        if self._command_listener:
            self._command_listener.stop()

        # Close Redis connection
        if self._redis:
            try:
                await self._redis.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.warning(f"Error closing Redis: {e}")

        # Stop health API server
        if self._health_runner:
            try:
                await self._health_runner.cleanup()
                logger.info("Health API server stopped")
            except Exception as e:
                logger.warning(f"Error stopping health API: {e}")

        # Close database connection pool
        if self.db:
            try:
                await self.db.dispose()
                logger.info("Database connection pool closed")
            except Exception as e:
                logger.error(f"Error closing database: {e}")

        logger.info("Orchestrator cleanup complete")

    def stop(self) -> None:
        """Stop the orchestrator and all bots."""
        logger.info("Stopping orchestrator...")
        self._running = False

        for task in self._tasks:
            if not task.done():
                task.cancel()

    def pause_bot(self, bot_name: str) -> bool:
        """Pause a specific bot.

        Args:
            bot_name: Name of bot to pause

        Returns:
            True if paused, False if bot not found
        """
        if bot_name not in self.bot_registry:
            return False

        self.bot_registry[bot_name]._set_paused(True)
        return True

    def resume_bot(self, bot_name: str) -> bool:
        """Resume a specific bot.

        Args:
            bot_name: Name of bot to resume

        Returns:
            True if resumed, False if bot not found
        """
        if bot_name not in self.bot_registry:
            return False

        self.bot_registry[bot_name]._set_paused(False)
        return True

    def _register_command_handlers(self) -> None:
        """Register handlers for Redis commands from the API service."""
        if not self._command_listener:
            return

        self._command_listener.register_handler("start_bot", self._handle_start_bot)
        self._command_listener.register_handler("pause_bot", self._handle_pause_bot)
        self._command_listener.register_handler("resume_bot", self._handle_resume_bot)
        self._command_listener.register_handler("stop_bot", self._handle_stop_bot)
        self._command_listener.register_handler("get_status", self._handle_get_status)
        logger.debug("Command handlers registered")

    async def _handle_start_bot(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle start_bot command from API — dynamically create and start a bot."""
        from trading_automata.config.bot_config import BotConfig, BrokerConfig, AllocationConfig, FenceConfig, RiskConfig

        bot_name = data.get("bot_name", "")
        user_id = data.get("user_id")
        config = data.get("config", {})

        if bot_name in self.bot_registry:
            raise ValueError(f"Bot '{bot_name}' is already running")

        try:
            # Publish "starting" status
            if self._event_publisher:
                await self._event_publisher.publish_bot_status_changed(
                    bot_name, "starting", user_id=user_id,
                )
                await self._event_publisher.update_bot_status(
                    bot_name, {"running": False, "paused": False, "starting": True,
                               "broker": config.get("broker_type", ""), "error": None},
                    user_id=user_id,
                )

            # Build BotConfig from API-provided config (credentials decrypted by API)
            bot_cfg = BotConfig(
                name=bot_name,
                enabled=True,
                broker=BrokerConfig(
                    type=config["broker_type"],
                    environment=config["environment"],
                    api_key=config["api_key"],
                    secret_key=config["secret_key"],
                    passphrase=config.get("passphrase", ""),
                ),
                allocation=AllocationConfig(
                    amount=config.get("allocation", 10000),
                ),
                fence=FenceConfig(
                    type=config.get("fence_type", "hard"),
                ),
                risk=RiskConfig(
                    stop_loss_pct=config.get("stop_loss_pct", 2.0),
                    take_profit_pct=config.get("take_profit_pct", 6.0),
                    max_position_size=config.get("max_position_size", 0.1),
                ),
                strategy_config=config.get("strategy_id", ""),
            )

            # Create bot-scoped Telegram if available
            bot_telegram = None
            if self.telegram_bot:
                bot_telegram = BotScopedTelegram(self.telegram_bot, bot_name)

            bot_instance = BotInstance(
                config=bot_cfg,
                db=self.db,
                trade_repo=self.trade_repo,
                health_checks=self.health_checks,
                event_logger=self.event_logger,
                telegram_bot=bot_telegram,
                session_factory=self.db.session_factory,
            )

            if await bot_instance.setup():
                self.bot_instances.append(bot_instance)
                self.bot_registry[bot_name] = bot_instance

                # Start bot in background
                task = asyncio.create_task(bot_instance.start())
                self._tasks.append(task)

                if self._event_publisher:
                    await self._event_publisher.publish_bot_status_changed(
                        bot_name, "running", user_id=user_id,
                    )

                logger.info(f"Bot '{bot_name}' started dynamically via API")
                return {"bot_name": bot_name, "status": "running"}
            else:
                error_msg = f"Bot '{bot_name}' setup failed"
                logger.error(error_msg)
                if self._event_publisher:
                    await self._event_publisher.publish_bot_status_changed(
                        bot_name, "failed", user_id=user_id,
                    )
                    await self._event_publisher.update_bot_status(
                        bot_name, {"running": False, "paused": False, "starting": False,
                                   "error": error_msg},
                        user_id=user_id,
                    )
                raise ValueError(error_msg)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to start bot '{bot_name}': {error_msg}", exc_info=True)
            if self._event_publisher:
                await self._event_publisher.publish_bot_status_changed(
                    bot_name, "failed", user_id=user_id, error=error_msg,
                )
                await self._event_publisher.update_bot_status(
                    bot_name, user_id=user_id,
                    status_data={"running": False, "paused": False, "starting": False,
                                 "error": error_msg},
                )
            raise

    async def _handle_pause_bot(self, data: Dict[str, Any]) -> Dict[str, Any]:
        bot_name = data.get("bot_name", "")
        if self.pause_bot(bot_name):
            if self._event_publisher:
                await self._event_publisher.publish_bot_status_changed(
                    bot_name, "paused", user_id=data.get("user_id"),
                )
            return {"bot_name": bot_name, "status": "paused"}
        raise ValueError(f"Bot '{bot_name}' not found")

    async def _handle_resume_bot(self, data: Dict[str, Any]) -> Dict[str, Any]:
        bot_name = data.get("bot_name", "")
        if self.resume_bot(bot_name):
            if self._event_publisher:
                await self._event_publisher.publish_bot_status_changed(
                    bot_name, "running", user_id=data.get("user_id"),
                )
            return {"bot_name": bot_name, "status": "running"}
        raise ValueError(f"Bot '{bot_name}' not found")

    async def _handle_stop_bot(self, data: Dict[str, Any]) -> Dict[str, Any]:
        bot_name = data.get("bot_name", "")
        if bot_name in self.bot_registry:
            self.bot_registry[bot_name].stop()
            if self._event_publisher:
                await self._event_publisher.publish_bot_status_changed(
                    bot_name, "stopped", user_id=data.get("user_id"),
                )
            return {"bot_name": bot_name, "status": "stopped"}
        raise ValueError(f"Bot '{bot_name}' not found")

    async def _handle_get_status(self, data: Dict[str, Any]) -> Dict[str, Any]:
        bot_name = data.get("bot_name")
        return self.get_bot_status(bot_name)

    async def _metrics_loop(self) -> None:
        """Periodically update Prometheus fleet gauges."""
        from datetime import datetime, UTC
        try:
            while self._running:
                counts = {"running": 0, "paused": 0, "stopped": 0, "faulty": 0}
                now = datetime.now(UTC)
                for name, bot in self.bot_registry.items():
                    if bot.is_faulty:
                        counts["faulty"] += 1
                    elif bot._paused:
                        counts["paused"] += 1
                    elif bot._running:
                        counts["running"] += 1
                    else:
                        counts["stopped"] += 1

                    age = (now - bot._last_heartbeat).total_seconds()
                    engine_heartbeat_age_seconds.labels(bot_name=name).set(age)

                for state, count in counts.items():
                    engine_bots_total.labels(state=state).set(count)

                # Refresh engine heartbeat in Redis
                if self._redis:
                    try:
                        await self._redis.set("engine:heartbeat", "ok", ex=30)
                    except Exception:
                        pass

                await asyncio.sleep(15)  # Update every 15 seconds
        except asyncio.CancelledError:
            pass

    def get_bot_status(self, bot_name: Optional[str] = None) -> dict:
        """Get status of one or all bots.

        Args:
            bot_name: Specific bot name, or None for all bots

        Returns:
            dict: Status information
        """
        if bot_name:
            if bot_name not in self.bot_registry:
                return {}

            bot = self.bot_registry[bot_name]
            return {
                bot_name: self._bot_status_dict(bot),
            }
        else:
            return {
                name: self._bot_status_dict(bot)
                for name, bot in self.bot_registry.items()
            }

    @staticmethod
    def _bot_status_dict(bot: BotInstance) -> dict:
        """Build status dict for a single bot."""
        return {
            'running': bot._running,
            'paused': bot._paused,
            'faulty': bot.is_faulty,
            'faulty_reason': bot._faulty_reason,
            'broker': bot.config.broker.type,
            'allocation': float(bot.portfolio_manager.allocated_capital if bot.portfolio_manager else 0),
            'virtual_balance': float(bot.portfolio_manager.virtual_balance if bot.portfolio_manager else 0),
            'fence_type': bot.config.fence.type,
            'evaluation_cycles': bot._evaluation_count,
            'consecutive_broker_errors': bot._consecutive_broker_errors,
        }
