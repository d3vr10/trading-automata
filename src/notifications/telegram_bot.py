"""Telegram bot for trading bot monitoring and control.

Provides:
- Real-time status updates
- Trade notifications
- Performance metrics
- Bot control (pause/resume)
- Health alerts
"""

import logging
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


class TradingBotTelegram:
    """Telegram bot interface for trading bot management."""

    def __init__(self, token: str, chat_id: str):
        """Initialize Telegram bot.

        Args:
            token: Telegram bot token from BotFather
            chat_id: Telegram chat ID to send messages to
        """
        self.token = token
        self.chat_id = chat_id
        self.application: Optional[Application] = None
        self._bot = None

        if not token:
            logger.warning("Telegram token not configured - bot notifications disabled")

    async def initialize(self) -> bool:
        """Initialize Telegram bot application.

        Returns:
            True if initialized successfully, False otherwise.
        """
        if not self.token:
            logger.warning("Telegram not configured - skipping initialization")
            return False

        try:
            self.application = Application.builder().token(self.token).build()

            # Add command handlers
            self.application.add_handler(
                CommandHandler("status", self._cmd_status)
            )
            self.application.add_handler(
                CommandHandler("trades", self._cmd_trades)
            )
            self.application.add_handler(
                CommandHandler("metrics", self._cmd_metrics)
            )
            self.application.add_handler(
                CommandHandler("pause", self._cmd_pause)
            )
            self.application.add_handler(
                CommandHandler("resume", self._cmd_resume)
            )
            self.application.add_handler(
                CommandHandler("help", self._cmd_help)
            )
            self.application.add_handler(
                CommandHandler("version", self._cmd_version)
            )
            self.application.add_handler(
                CommandHandler("uptime", self._cmd_uptime)
            )

            # Set bot commands
            await self._set_commands()

            logger.info("✅ Telegram bot initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            return False

    async def _set_commands(self) -> None:
        """Set available bot commands in Telegram UI."""
        commands = [
            BotCommand("status", "Show bot status and portfolio"),
            BotCommand("trades", "Show recent trades"),
            BotCommand("metrics", "Show performance metrics"),
            BotCommand("version", "Show bot version"),
            BotCommand("uptime", "Show bot uptime"),
            BotCommand("pause", "Pause trading"),
            BotCommand("resume", "Resume trading"),
            BotCommand("help", "Show available commands"),
        ]
        try:
            await self.application.bot.set_my_commands(commands)
        except Exception as e:
            logger.warning(f"Could not set bot commands: {e}")

    async def send_message(self, text: str, parse_mode=ParseMode.HTML) -> bool:
        """Send message to configured chat.

        Args:
            text: Message text
            parse_mode: How to parse message (HTML, MARKDOWN, etc.)

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.token or not self.chat_id:
            return False

        try:
            if not self.application:
                await self.initialize()

            await self.application.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode,
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def send_trade_alert(
        self,
        symbol: str,
        side: str,
        price: Decimal,
        quantity: Decimal,
        strategy: str,
    ) -> None:
        """Send trade execution alert.

        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell'
            price: Entry/exit price
            quantity: Trade quantity
            strategy: Strategy name
        """
        side_emoji = "📈" if side.lower() == "buy" else "📉"
        message = f"""{side_emoji} <b>Trade Executed</b>

<b>Symbol:</b> {symbol}
<b>Side:</b> {side.upper()}
<b>Price:</b> ${float(price):.2f}
<b>Quantity:</b> {float(quantity):.4f}
<b>Strategy:</b> {strategy}
<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}
"""
        await self.send_message(message)

    async def send_performance_alert(
        self, win_rate: float, profit_factor: float, total_trades: int
    ) -> None:
        """Send performance update.

        Args:
            win_rate: Winning trades percentage
            profit_factor: Profit factor ratio
            total_trades: Total trades executed
        """
        emoji = "✅" if win_rate > 50 else "⚠️"
        message = f"""{emoji} <b>Performance Update</b>

<b>Total Trades:</b> {total_trades}
<b>Win Rate:</b> {win_rate:.1f}%
<b>Profit Factor:</b> {profit_factor:.2f}
<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}
"""
        await self.send_message(message)

    async def send_error_alert(self, error_type: str, message: str) -> None:
        """Send error/warning alert.

        Args:
            error_type: Type of error (connection, execution, etc.)
            message: Error message
        """
        alert = f"""🚨 <b>Trading Bot Alert</b>

<b>Type:</b> {error_type}
<b>Message:</b> {message}
<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}
"""
        await self.send_message(alert)

    async def send_health_alert(
        self, is_healthy: bool, status: Dict[str, Any]
    ) -> None:
        """Send health check alert.

        Args:
            is_healthy: Bot health status
            status: Health status dictionary
        """
        emoji = "🟢" if is_healthy else "🔴"
        errors = status.get("connection_errors", 0)

        message = f"""{emoji} <b>Health Check</b>

<b>Status:</b> {'HEALTHY' if is_healthy else 'UNHEALTHY'}
<b>Connection Errors:</b> {errors}
<b>Last Bar:</b> {status.get('last_bar_timestamp', 'N/A')}
<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}
"""
        await self.send_message(message)

    # Command handlers

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        message = """📊 <b>Trading Bot Status</b>

<i>Status handler will be implemented when integrated with main bot</i>

<b>Placeholder Info:</b>
• Bot: Running
• Strategy: RSI-ATR Trend
• Broker: Alpaca (Paper)
"""
        await update.message.reply_html(message)

    async def _cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trades command."""
        message = """📈 <b>Recent Trades</b>

<i>Trade history will be fetched from database when integrated</i>

<b>Placeholder:</b>
Last 5 trades will appear here
"""
        await update.message.reply_html(message)

    async def _cmd_metrics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /metrics command."""
        message = """📊 <b>Performance Metrics</b>

<i>Metrics will be fetched from database when integrated</i>

<b>Placeholder:</b>
Win Rate, Profit Factor, Sharpe Ratio will appear here
"""
        await update.message.reply_html(message)

    async def _cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pause command."""
        message = """⏸️ <b>Pause Trading</b>

Trading has been paused. The bot will stop executing new trades.
Current positions will remain open.
"""
        await update.message.reply_html(message)

    async def _cmd_resume(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /resume command."""
        message = """▶️ <b>Resume Trading</b>

Trading has been resumed. The bot will resume executing trades.
"""
        await update.message.reply_html(message)

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        message = """❓ <b>Available Commands</b>

<b>/status</b> - Show bot status and portfolio
<b>/trades</b> - Show recent trades (last 10)
<b>/metrics</b> - Show performance metrics
<b>/version</b> - Show bot version
<b>/uptime</b> - Show bot uptime
<b>/pause</b> - Pause trading
<b>/resume</b> - Resume trading
<b>/help</b> - Show this help message

<i>Use /start to see all commands</i>
"""
        await update.message.reply_html(message)

    async def _cmd_version(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /version command."""
        try:
            import tomllib  # Python 3.11+
        except ModuleNotFoundError:
            import tomli as tomllib  # Fallback for older Python

        try:
            with open('pyproject.toml', 'rb') as f:
                project_data = tomllib.load(f)
                version_str = project_data.get('project', {}).get('version', 'unknown')
        except FileNotFoundError:
            version_str = 'unknown'

        message = f"""🤖 <b>Trading Bot Version</b>

<b>Version:</b> <code>{version_str}</code>
<b>Timestamp:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}
"""
        await update.message.reply_html(message)

    async def _cmd_uptime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /uptime command."""
        message = """⏱️ <b>Bot Uptime</b>

<i>Uptime calculation requires database connection.</i>
<i>Please use CLI command: python -m src.cli uptime</i>

<b>Placeholder:</b>
Uptime will be displayed when integrated with main bot
"""
        await update.message.reply_html(message)

    async def start(self) -> None:
        """Start the bot polling (background task)."""
        if not self.application:
            return

        try:
            logger.info("Starting Telegram bot polling...")
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            logger.info("✅ Telegram bot polling started")
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")

    async def stop(self) -> None:
        """Stop the bot."""
        if not self.application:
            return

        try:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram bot stopped")
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {e}")
