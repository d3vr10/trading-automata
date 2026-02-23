"""Multi-bot orchestrator for concurrent bot management.

Owns shared infrastructure (database, Telegram) and coordinates lifecycle
for all BotInstance objects.
"""

import asyncio
import logging
from typing import Dict, List, Optional

from trading_bot.config.loader import load_bot_configs
from trading_bot.config.bot_config import OrchestratorConfig
from trading_bot.database.models import DatabaseConnection
from trading_bot.database.repository import TradeRepository
from trading_bot.database.health import HealthCheckRegistry
from trading_bot.monitoring.event_logger import init_event_logger, get_event_logger
from trading_bot.monitoring.logger import get_logger
from trading_bot.notifications.telegram_bot import TradingBotTelegram, BotScopedTelegram
from trading_bot.orchestration.bot_instance import BotInstance


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
        self.bot_registry: Dict[str, BotInstance] = {}  # For Telegram commands
        self._tasks: List[asyncio.Task] = []
        self._running = False

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
            logger.info(f"Setting up {len(self.orchestrator_config.bots)} bot instance(s)...")
            successful_bots = 0

            for bot_cfg in self.orchestrator_config.bots:
                if not bot_cfg.enabled:
                    logger.info(f"Bot '{bot_cfg.name}' is disabled, skipping")
                    continue

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

            if successful_bots == 0:
                logger.error("No bots were successfully initialized")
                return False

            logger.info(f"Setup complete: {successful_bots} bot(s) ready")
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
            # Start Telegram bot polling in background (if configured)
            telegram_task = None
            if self.telegram_bot:
                logger.info("Starting Telegram bot...")
                telegram_task = asyncio.create_task(self.telegram_bot.start())
                self._tasks.append(telegram_task)

            # Start all bot instances in parallel
            logger.info(f"Starting {len(self.bot_instances)} bot instance(s)...")
            for bot_instance in self.bot_instances:
                task = asyncio.create_task(bot_instance.start())
                self._tasks.append(task)

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
                bot_name: {
                    'running': bot._running,
                    'paused': bot._paused,
                    'broker': bot.config.broker.type,
                    'allocation': float(bot.portfolio_manager.allocated_capital if bot.portfolio_manager else 0),
                    'virtual_balance': float(bot.portfolio_manager.virtual_balance if bot.portfolio_manager else 0),
                    'fence_type': bot.config.fence.type,
                }
            }
        else:
            status = {}
            for name, bot in self.bot_registry.items():
                status[name] = {
                    'running': bot._running,
                    'paused': bot._paused,
                    'broker': bot.config.broker.type,
                    'allocation': float(bot.portfolio_manager.allocated_capital if bot.portfolio_manager else 0),
                    'virtual_balance': float(bot.portfolio_manager.virtual_balance if bot.portfolio_manager else 0),
                    'fence_type': bot.config.fence.type,
                }
            return status
