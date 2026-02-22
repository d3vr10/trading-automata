"""Telegram bot for trading bot monitoring and control.

Provides:
- Real-time status updates
- Trade notifications
- Performance metrics
- Bot control (pause/resume)
- Health alerts
"""

import logging
from typing import Optional, Dict, Any, Callable
from decimal import Decimal
from datetime import datetime, UTC

from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)
from telegram.constants import ParseMode
from sqlalchemy import select, func, and_
from trading_bot.database.models import DatabaseConnection, BotSession, Trade, Position, HealthCheck
from trading_bot.database.repository import TradeRepository
from trading_bot.brokers.base import IBroker
from trading_bot.utils.chart_generator import ChartGenerator

logger = logging.getLogger(__name__)


class TradingBotTelegram:
    """Telegram bot interface for trading bot management."""

    def __init__(
        self,
        token: str,
        chat_id: Optional[str | list[str]] = None,
        username_whitelist: Optional[list[str]] = None,
        database_url: Optional[str] = None,
        broker: Optional[IBroker] = None,
        on_pause: Optional[Callable[[], Any]] = None,
        on_resume: Optional[Callable[[], Any]] = None,
        webhook_url: str = '',
        webhook_secret: str = '',
        webhook_port: int = 8080,
        pool_size: int = 10,
        max_overflow: int = 20,
    ):
        """Initialize Telegram bot.

        Args:
            token: Telegram bot token from BotFather
            chat_id: Telegram chat ID(s) to send messages to (for notifications).
                    Can be a single string or list of strings.
                    Example: "123456789" or ["123456789", "987654321"]
            username_whitelist: List of Telegram usernames allowed to use bot commands
                               REQUIRED: If not provided or empty, all commands will be rejected.
                               Example: ['username1', 'username2']
            database_url: PostgreSQL connection URL for accessing bot data
            broker: Optional broker instance for position/order management
            on_pause: Optional callback to execute when /pause is called
            on_resume: Optional callback to execute when /resume is called
            webhook_url: Webhook URL for production (e.g., https://example.com)
            webhook_secret: Secret token for webhook validation
            webhook_port: Port for webhook server to listen on (default 8080)
            pool_size: Database connection pool size
            max_overflow: Database connection pool overflow size
        """
        self.token = token
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret
        self.webhook_port = webhook_port

        # Convert single chat_id to list, or use empty list if None
        if isinstance(chat_id, str):
            self.chat_ids = [chat_id]
        elif isinstance(chat_id, list):
            self.chat_ids = chat_id
        else:
            self.chat_ids = []

        self.username_whitelist = set(u.lstrip('@').lower() for u in (username_whitelist or []))
        self.database_url = database_url
        self.broker = broker
        self._on_pause = on_pause
        self._on_resume = on_resume
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.database: Optional[DatabaseConnection] = None
        self.application: Optional[Application] = None
        self._bot = None
        self._paused = False  # Track pause/resume state

        if not token:
            logger.warning("Telegram token not configured - bot notifications disabled")

        if self.username_whitelist:
            logger.info(f"Telegram whitelist enabled: {', '.join(self.username_whitelist)}")
        else:
            logger.warning("Telegram username whitelist not configured - bot commands will be rejected")

        if self.chat_ids:
            logger.info(f"Telegram notifications enabled for {len(self.chat_ids)} chat(s)")

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
            self.application.add_handler(
                CommandHandler("broker_positions", self._cmd_broker_positions)
            )
            self.application.add_handler(
                CommandHandler("broker_orders", self._cmd_broker_orders)
            )
            self.application.add_handler(
                CommandHandler("close_position", self._cmd_close_position)
            )
            self.application.add_handler(
                CommandHandler("close_all_positions", self._cmd_close_all_positions)
            )
            self.application.add_handler(
                CommandHandler("cancel_order", self._cmd_cancel_order)
            )
            self.application.add_handler(
                CommandHandler("cancel_orders", self._cmd_cancel_orders)
            )
            self.application.add_handler(
                CommandHandler("close_strategy", self._cmd_close_strategy)
            )
            self.application.add_handler(
                CommandHandler("cancel_strategy", self._cmd_cancel_strategy)
            )
            self.application.add_handler(
                CommandHandler("strategies", self._cmd_strategies)
            )
            self.application.add_handler(
                CallbackQueryHandler(self._handle_trades_callback, pattern="^trades_")
            )
            self.application.add_handler(
                CallbackQueryHandler(self._handle_confirmation)
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
            BotCommand("strategies", "List available strategies"),
            BotCommand("version", "Show bot version"),
            BotCommand("uptime", "Show bot uptime"),
            BotCommand("pause", "Pause trading"),
            BotCommand("resume", "Resume trading"),
            BotCommand("broker_positions", "List open positions from broker"),
            BotCommand("broker_orders", "List open orders from broker"),
            BotCommand("close_position", "Close a position by symbol"),
            BotCommand("close_all_positions", "Close all open positions"),
            BotCommand("close_strategy", "Close all positions from a strategy"),
            BotCommand("cancel_order", "Cancel an order by ID"),
            BotCommand("cancel_orders", "Cancel multiple orders"),
            BotCommand("cancel_strategy", "Cancel all orders from a strategy"),
            BotCommand("help", "Show available commands"),
        ]
        try:
            await self.application.bot.set_my_commands(commands)
        except Exception as e:
            logger.warning(f"Could not set bot commands: {e}")

    async def send_message(self, text: str, parse_mode=ParseMode.HTML) -> bool:
        """Send message to configured chat(s).

        Args:
            text: Message text
            parse_mode: How to parse message (HTML, MARKDOWN, etc.)

        Returns:
            True if sent successfully to at least one chat, False otherwise.
        """
        if not self.token or not self.chat_ids:
            return False

        try:
            if not self.application:
                await self.initialize()

            success_count = 0
            for chat_id in self.chat_ids:
                try:
                    await self.application.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode=parse_mode,
                    )
                    success_count += 1
                except Exception as e:
                    logger.warning(f"Failed to send message to chat {chat_id}: {e}")

            return success_count > 0

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
<b>Time:</b> {datetime.now(UTC).strftime('%H:%M:%S UTC')}
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
<b>Time:</b> {datetime.now(UTC).strftime('%H:%M:%S UTC')}
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
<b>Time:</b> {datetime.now(UTC).strftime('%H:%M:%S UTC')}
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
<b>Time:</b> {datetime.now(UTC).strftime('%H:%M:%S UTC')}
"""
        await self.send_message(message)

    # Authorization

    async def _check_authorized(self, update: Update) -> bool:
        """Check if user is authorized to use bot commands.

        Args:
            update: Telegram update with user info

        Returns:
            True if authorized, False otherwise
        """
        # If no whitelist configured, reject all command attempts
        if not self.username_whitelist:
            user = update.effective_user
            username = f"@{user.username}" if user and user.username else "unknown user"
            await update.message.reply_text(
                "❌ <b>Not Authorized</b>\n\n"
                "Bot commands are not available. "
                "Administrator must configure TELEGRAM_USERNAME_WHITELIST to enable this feature.",
                parse_mode=ParseMode.HTML,
            )
            logger.warning(f"Command rejected: no whitelist configured (user: {username})")
            return False

        # Check if user is in whitelist
        user = update.effective_user
        if not user or not user.username:
            await update.message.reply_text(
                "❌ <b>Not Authorized</b>\n\n"
                "You must have a Telegram username to use this bot.",
                parse_mode=ParseMode.HTML,
            )
            logger.warning(f"Unauthorized command attempt from user without username")
            return False

        username = user.username.lower()
        if username not in self.username_whitelist:
            await update.message.reply_text(
                f"❌ <b>Not Authorized</b>\n\n"
                f"User <code>@{username}</code> is not whitelisted to use this bot.",
                parse_mode=ParseMode.HTML,
            )
            logger.warning(f"Unauthorized command attempt from @{username}")
            return False

        return True

    # Command handlers

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        if not await self._check_authorized(update):
            return

        try:
            # Initialize database if needed
            if not self.database and self.database_url:
                self.database = DatabaseConnection(
                    database_url=self.database_url,
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                )

            message = "📊 <b>Trading Bot Status</b>\n\n"

            # Get broker account info
            if self.broker:
                try:
                    account = self.broker.get_account()
                    message += f"💰 <b>Account</b>\n"
                    message += f"  Portfolio Value: ${float(account.get('portfolio_value', 0)):,.2f}\n"
                    message += f"  Buying Power: ${float(account.get('buying_power', 0)):,.2f}\n"
                    message += f"  Cash: ${float(account.get('cash', 0)):,.2f}\n"
                    if account.get('equity'):
                        message += f"  Equity: ${float(account['equity']):,.2f}\n"
                    message += "\n"
                except Exception as e:
                    logger.warning(f"Failed to get account info: {e}")

            # Get open positions
            if self.database:
                async with self.database.session_factory() as session:
                    # Get open positions
                    stmt = select(Position).where(Position.is_open == True)
                    result = await session.execute(stmt)
                    positions = result.scalars().all()

                    # Get latest trade
                    stmt = select(Trade).order_by(Trade.entry_timestamp.desc()).limit(1)
                    result = await session.execute(stmt)
                    latest_trade = result.scalar_one_or_none()

                    # Get health status
                    stmt = select(HealthCheck).order_by(HealthCheck.checked_at.desc()).limit(1)
                    result = await session.execute(stmt)
                    health = result.scalar_one_or_none()

            message += f"<b>Status:</b> {'🟢 RUNNING' if not self._paused else '🟡 PAUSED'}\n"
            message += f"<b>Open Positions:</b> {len(positions) if self.database else 'N/A'}\n"

            if positions:
                total_pnl = sum(float(p.unrealized_pnl or 0) for p in positions)
                message += f"<b>Unrealized P&L:</b> ${total_pnl:,.2f}\n\n"
                message += "<b>Positions:</b>\n"
                for pos in positions:
                    message += f"• {pos.symbol}: {float(pos.quantity)} @ ${float(pos.entry_price)}\n"

            if latest_trade:
                message += f"\n<b>Last Trade:</b> {latest_trade.symbol} - {latest_trade.entry_timestamp.strftime('%H:%M:%S')}\n"

            if health:
                message += f"<b>Health:</b> {'🟢 Healthy' if health.is_healthy else '🔴 Unhealthy'}\n"

            await update.message.reply_html(message)

        except Exception as e:
            logger.error(f"Error in /status command: {e}")
            await update.message.reply_text(f"❌ Error retrieving status: {str(e)}")

    async def _cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trades command with optional filters.

        Usage:
            /trades                    - Show all trades (open and closed)
            /trades open               - Show only open trades
            /trades closed             - Show only closed trades
            /trades rsi_atr_trend      - Show trades for specific strategy
            /trades rsi_atr_trend open - Show open trades for specific strategy
            /trades momentum closed    - Show closed trades for momentum strategy
        """
        if not await self._check_authorized(update):
            return

        try:
            if not self.database and self.database_url:
                self.database = DatabaseConnection(
                    database_url=self.database_url,
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                )

            # Parse filters from args
            status_filter = None
            strategy_filter = None

            if context.args:
                for arg in context.args:
                    arg_lower = arg.lower()
                    if arg_lower in ('open', 'closed'):
                        status_filter = arg_lower
                    else:
                        # Assume it's a strategy name
                        strategy_filter = arg_lower

            message = "📈 <b>Recent Trades</b>\n"
            if strategy_filter or status_filter:
                filters = []
                if strategy_filter:
                    filters.append(f"Strategy: {strategy_filter}")
                if status_filter:
                    filters.append(f"Status: {status_filter.upper()}")
                message += f"({', '.join(filters)})\n"
            message += "\n"

            if not self.database:
                message += "<i>Database not configured</i>"
                if update.callback_query:
                    await update.callback_query.edit_message_text(message, parse_mode='HTML')
                else:
                    await update.message.reply_html(message)
                return

            async with self.database.session_factory() as session:
                # Build WHERE clauses for filters
                closed_where = [Trade.exit_order_id != None]
                open_where = [Trade.exit_order_id == None]

                if strategy_filter:
                    closed_where.append(Trade.strategy.ilike(f"%{strategy_filter}%"))
                    open_where.append(Trade.strategy.ilike(f"%{strategy_filter}%"))

                # Get closed trades
                from sqlalchemy import and_
                stmt = (
                    select(Trade)
                    .where(and_(*closed_where))
                    .order_by(Trade.entry_timestamp.desc())
                    .limit(20)
                )
                result = await session.execute(stmt)
                closed_trades = result.scalars().all()

                # Get open trades
                stmt_open = (
                    select(Trade)
                    .where(and_(*open_where))
                    .order_by(Trade.entry_timestamp.desc())
                    .limit(20)
                )
                result_open = await session.execute(stmt_open)
                open_trades = result_open.scalars().all()

            if not closed_trades and not open_trades:
                message += "<i>No trades found</i>"
            else:
                # Show closed trades (if not filtered to open only)
                if status_filter != 'open' and closed_trades:
                    message += f"<b>✅ Closed Trades ({len(closed_trades)}):</b>\n\n"
                    for trade in closed_trades:
                        pnl_emoji = "✅" if trade.is_winning_trade else "❌"
                        pnl_str = f"${float(trade.gross_pnl):,.2f}" if trade.gross_pnl else "N/A"
                        pnl_pct = f" ({float(trade.pnl_percent):.1f}%)" if trade.pnl_percent else ""

                        message += (
                            f"{pnl_emoji} <b>{trade.symbol}</b>\n"
                            f"  Entry: ${float(trade.entry_price):.4f} × {float(trade.entry_quantity)}\n"
                            f"  Exit: ${float(trade.exit_price):.4f} × {float(trade.exit_quantity)}\n"
                            f"  P&L: {pnl_str}{pnl_pct}\n"
                            f"  Strategy: {trade.strategy}\n\n"
                        )
                elif status_filter != 'open' and not closed_trades and (not strategy_filter or status_filter):
                    message += "<i>No closed trades found</i>\n\n"

                # Show open trades (if not filtered to closed only)
                if status_filter != 'closed' and open_trades:
                    message += f"<b>📈 Open Trades ({len(open_trades)}):</b>\n\n"
                    for trade in open_trades:
                        message += (
                            f"📈 <b>{trade.symbol}</b>\n"
                            f"  Entry: ${float(trade.entry_price):.4f} × {float(trade.entry_quantity)}\n"
                            f"  Strategy: {trade.strategy}\n"
                            f"  Awaiting exit...\n\n"
                        )
                elif status_filter != 'closed' and not open_trades and (not strategy_filter or status_filter):
                    message += "<i>No open trades found</i>\n"

            # Build inline keyboard for quick filtering
            keyboard = []

            # Status filter row
            status_buttons = [
                InlineKeyboardButton("📈 Open", callback_data="trades_open"),
                InlineKeyboardButton("✅ Closed", callback_data="trades_closed"),
                InlineKeyboardButton("📊 All", callback_data="trades_all"),
            ]
            keyboard.append(status_buttons)

            # Strategy filter row (from config)
            try:
                import yaml
                from pathlib import Path
                config_path = Path('config/strategies.yaml')
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                    strategies = config.get('strategies', [])
                    strategy_buttons = []
                    for strat in strategies[:4]:  # Limit to 4 strategies per row
                        name = strat.get('name', '')
                        enabled = strat.get('enabled', True)
                        if enabled and name:
                            # Truncate long names for button display
                            short_name = name.split('_')[0].upper()
                            strategy_buttons.append(
                                InlineKeyboardButton(short_name, callback_data=f"trades_strat_{name}")
                            )
                    if strategy_buttons:
                        keyboard.append(strategy_buttons)
            except Exception:
                pass  # If config loading fails, just skip strategy buttons

            reply_markup = InlineKeyboardMarkup(keyboard)

            # Handle both regular messages and callback queries
            if update.callback_query:
                # Called from button callback - edit existing message
                await update.callback_query.edit_message_text(
                    message,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            else:
                # Called as regular command - send new message
                await update.message.reply_html(message, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error in /trades command: {e}")
            if update.callback_query:
                await update.callback_query.edit_message_text(f"❌ Error retrieving trades: {str(e)}")
            else:
                await update.message.reply_text(f"❌ Error retrieving trades: {str(e)}")

    async def _cmd_metrics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /metrics command with charts."""
        if not await self._check_authorized(update):
            return

        try:
            if not self.database and self.database_url:
                self.database = DatabaseConnection(
                    database_url=self.database_url,
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                )

            if not self.database:
                await update.message.reply_text("❌ Database not configured")
                return

            # Show "generating charts" message
            await update.message.reply_text("📊 Generating performance charts...")

            async with self.database.session_factory() as session:
                # Get all closed trades
                stmt = select(Trade).where(Trade.exit_order_id != None)
                result = await session.execute(stmt)
                all_trades = result.scalars().all()

                # Get open trades
                stmt = select(Trade).where(Trade.exit_order_id == None)
                result = await session.execute(stmt)
                open_trades = result.scalars().all()

            if not all_trades and not open_trades:
                await update.message.reply_text("ℹ️ No trades yet")
                return

            # Generate P&L chart
            pnl_image, pnl_metrics = ChartGenerator.generate_pnl_chart(all_trades)

            # Generate performance summary chart
            perf_image = ChartGenerator.generate_performance_chart(all_trades, open_trades)

            # Send P&L chart
            if pnl_image:
                await update.message.reply_photo(
                    photo=pnl_image,
                    caption="📈 <b>P&L Over Time</b>",
                    parse_mode="HTML"
                )

            # Send performance summary chart
            if perf_image:
                await update.message.reply_photo(
                    photo=perf_image,
                    caption="📊 <b>Performance Summary</b>",
                    parse_mode="HTML"
                )

            # Send text summary
            message = "📋 <b>Trade Summary</b>\n\n"

            if all_trades:
                total_trades = len(all_trades)
                winning_trades = sum(1 for t in all_trades if t.is_winning_trade)
                losing_trades = total_trades - winning_trades
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

                gross_profit = sum(float(t.gross_pnl or 0) for t in all_trades if t.gross_pnl and float(t.gross_pnl) > 0)
                gross_loss = abs(sum(float(t.gross_pnl or 0) for t in all_trades if t.gross_pnl and float(t.gross_pnl) < 0))
                profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
                total_pnl = gross_profit - gross_loss

                message += f"<b>Closed Trades:</b> {total_trades}\n"
                message += f"<b>Wins/Losses:</b> ✅ {winning_trades} / ❌ {losing_trades}\n"
                message += f"<b>Win Rate:</b> {win_rate:.1f}%\n"
                message += f"<b>Profit Factor:</b> {profit_factor:.2f if profit_factor != float('inf') else '∞'}\n"
                message += f"<b>Gross Profit:</b> ${gross_profit:,.2f}\n"
                message += f"<b>Gross Loss:</b> -${gross_loss:,.2f}\n"
                message += f"<b>Net P&L:</b> ${total_pnl:,.2f}\n"

                if pnl_metrics:
                    message += f"\n<b>Drawdown:</b> ${pnl_metrics.get('max_drawdown', 0):,.2f}\n"

            # Show open trades info
            message += f"\n<b>Open Positions:</b> {len(open_trades)}\n"
            if open_trades:
                total_entry_cost = sum(float(t.entry_price * t.entry_quantity or 0) for t in open_trades)
                message += f"<b>Total Entry Cost:</b> ${total_entry_cost:,.2f}\n"

            # Per-strategy breakdown
            strategies = {}
            for trade in all_trades:
                if trade.strategy not in strategies:
                    strategies[trade.strategy] = {"wins": 0, "total": 0, "pnl": 0}
                strategies[trade.strategy]["total"] += 1
                if trade.is_winning_trade:
                    strategies[trade.strategy]["wins"] += 1
                strategies[trade.strategy]["pnl"] += float(trade.gross_pnl or 0)

            if strategies:
                message += "\n<b>By Strategy:</b>\n"
                for strat, data in strategies.items():
                    wr = (data["wins"] / data["total"] * 100) if data["total"] > 0 else 0
                    message += f"• {strat}: {data['total']} trades, {wr:.0f}% WR, ${data['pnl']:,.2f}\n"

            await update.message.reply_html(message)

        except Exception as e:
            logger.error(f"Error in /metrics command: {e}")
            await update.message.reply_text(f"❌ Error retrieving metrics: {str(e)}")

    async def _cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pause command."""
        if not await self._check_authorized(update):
            return

        # Call pause callback if provided
        if self._on_pause:
            try:
                result = self._on_pause()
                # Handle async callbacks
                if hasattr(result, '__await__'):
                    await result
            except Exception as e:
                logger.error(f"Error calling pause callback: {e}")

        self._paused = True
        message = """⏸️ <b>Pause Trading</b>

✅ Trading has been paused. The bot will stop executing new trades.
Current positions will remain open.
"""
        await update.message.reply_html(message)
        logger.info(f"Trading paused by @{update.effective_user.username}")

    async def _cmd_resume(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /resume command."""
        if not await self._check_authorized(update):
            return

        # Call resume callback if provided
        if self._on_resume:
            try:
                result = self._on_resume()
                # Handle async callbacks
                if hasattr(result, '__await__'):
                    await result
            except Exception as e:
                logger.error(f"Error calling resume callback: {e}")

        self._paused = False
        message = """▶️ <b>Resume Trading</b>

✅ Trading has been resumed. The bot will resume executing trades.
"""
        await update.message.reply_html(message)
        logger.info(f"Trading resumed by @{update.effective_user.username}")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        if not await self._check_authorized(update):
            return

        message = """❓ <b>Available Commands</b>

<b>📊 Status & Portfolio:</b>
<b>/status</b> - Account balance, equity, buying power & open positions
<b>/trades [STRATEGY] [open|closed]</b> - Recent trades with quick filter buttons
  Examples: <code>/trades</code> <code>/trades open</code> <code>/trades rsi_atr_trend</code> <code>/trades momentum closed</code>
<b>/metrics</b> - Performance stats (win rate, profit factor, P&L breakdown)
<b>/strategies</b> - List all available strategies & status
<b>/uptime</b> - Bot process uptime

<b>🎮 Trading Control:</b>
<b>/pause</b> - Pause signal execution
<b>/resume</b> - Resume signal execution

<b>💼 Broker Management:</b>
<b>/broker_positions</b> - Broker's open positions (real-time)
<b>/broker_orders</b> - Broker's open orders (real-time)
<b>/close_position SYMBOL</b> - Close position (e.g. /close_position SPY)
<b>/close_all_positions</b> - Close all positions
<b>/close_strategy STRATEGY</b> - Close all positions from a strategy
<b>/cancel_order ID</b> - Cancel a specific order
<b>/cancel_orders [SYMBOL]</b> - Cancel all orders [for a symbol]
<b>/cancel_strategy STRATEGY</b> - Cancel all orders from a strategy

<b>ℹ️ Info:</b>
<b>/version</b> - Bot version & timestamp
<b>/help</b> - Show this help message
"""
        await update.message.reply_html(message)

    async def _cmd_version(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /version command."""
        if not await self._check_authorized(update):
            return

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
<b>Timestamp:</b> {datetime.now(UTC).strftime('%H:%M:%S UTC')}
"""
        await update.message.reply_html(message)

    async def _cmd_strategies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /strategies command - list available strategies."""
        if not await self._check_authorized(update):
            return

        try:
            import yaml
            from pathlib import Path

            # Load strategies from config
            config_path = Path('config/strategies.yaml')
            if not config_path.exists():
                await update.message.reply_text("❌ Strategies config file not found")
                return

            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            strategies = config.get('strategies', [])
            if not strategies:
                await update.message.reply_text("❌ No strategies configured")
                return

            message = "📊 <b>Available Strategies</b>\n\n"
            for strat in strategies:
                name = strat.get('name', 'unknown')
                enabled = strat.get('enabled', True)
                class_name = strat.get('class', 'N/A')
                symbols = ', '.join(strat.get('symbols', []))

                status_emoji = "✅" if enabled else "❌"
                message += f"{status_emoji} <b>{name}</b>\n"
                message += f"  Class: {class_name}\n"
                message += f"  Symbols: {symbols}\n\n"

            await update.message.reply_html(message)

        except Exception as e:
            logger.error(f"Error in /strategies command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _cmd_uptime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /uptime command."""
        if not await self._check_authorized(update):
            return

        if not self.database_url:
            message = """⏱️ <b>Bot Uptime</b>

Database not configured - cannot retrieve uptime.
"""
            await update.message.reply_html(message)
            return

        try:
            # Initialize database connection if not already done
            if not self.database:
                self.database = DatabaseConnection(
                    database_url=self.database_url,
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                )

            # Get latest bot session start time
            async with self.database.session_factory() as session:
                stmt = select(BotSession).order_by(BotSession.started_at.desc()).limit(1)
                result = await session.execute(stmt)
                bot_session = result.scalar_one_or_none()

            if bot_session:
                # Ensure timezone-aware datetime (add UTC if naive)
                start_time = bot_session.started_at
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=UTC)

                now = datetime.now(UTC)
                uptime_delta = now - start_time
                hours = uptime_delta.seconds // 3600
                minutes = (uptime_delta.seconds % 3600) // 60
                seconds = uptime_delta.seconds % 60
                days = uptime_delta.days

                message = f"""⏱️ <b>Bot Uptime</b>

<b>Started at:</b> {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}
<b>Current time:</b> {now.strftime('%Y-%m-%d %H:%M:%S UTC')}
<b>Uptime:</b> {days}d {hours}h {minutes}m {seconds}s
"""
            else:
                message = """⏱️ <b>Bot Uptime</b>

No bot session found - bot may not have started yet.
"""

            await update.message.reply_html(message)
        except Exception as e:
            logger.error(f"Failed to get uptime: {e}")
            message = f"Error retrieving uptime: {str(e)}"
            await update.message.reply_text(message)

    # Broker Management Commands

    async def _cmd_broker_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /broker_positions command."""
        if not await self._check_authorized(update):
            return

        if not self.broker:
            await update.message.reply_text("❌ Broker not configured")
            return

        try:
            positions = self.broker.get_positions()

            if not positions:
                message = "📊 <b>Open Positions</b>\n\n<i>No open positions</i>"
                await update.message.reply_html(message)
                return

            message = f"📊 <b>Open Positions ({len(positions)})</b>\n\n"
            for i, pos in enumerate(positions, 1):
                symbol = pos.get('symbol', 'N/A')
                qty = float(pos.get('qty', 0))
                entry_price = float(pos.get('avg_fill_price', 0))
                current_price = float(pos.get('current_price', 0))
                pnl = float(pos.get('unrealized_pl', 0))
                pnl_color = "🟢" if pnl >= 0 else "🔴"

                message += f"{i}. <b>{symbol}</b>\n"
                message += f"   Qty: {qty}\n"
                message += f"   Entry: ${entry_price:.4f}\n"
                message += f"   Current: ${current_price:.4f}\n"
                message += f"   P&L: {pnl_color} ${pnl:,.2f}\n\n"

            await update.message.reply_html(message)

        except Exception as e:
            logger.error(f"Error in /broker_positions: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _cmd_broker_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /broker_orders [SYMBOL] [STATUS] command with pagination."""
        if not await self._check_authorized(update):
            return

        if not self.broker:
            await update.message.reply_text("❌ Broker not configured")
            return

        try:
            # Parse pagination page (stored in context)
            page = 1
            if hasattr(context, 'user_data') and 'orders_page' in context.user_data:
                page = context.user_data['orders_page']

            # Parse optional symbol and status filters
            symbol_filter = None
            status_filter = None

            if context.args:
                for arg in context.args:
                    if arg.upper() in ('OPEN', 'CLOSED', 'PENDING', 'CANCELLED'):
                        status_filter = arg.lower()
                    elif arg.isdigit():
                        page = int(arg)
                    else:
                        symbol_filter = arg.upper()

            all_orders = self.broker.get_orders(status=status_filter)
            all_orders = all_orders[:100]  # Fetch up to 100 from broker

            if symbol_filter:
                all_orders = [o for o in all_orders if o.get('symbol', '').upper().startswith(symbol_filter)]

            if not all_orders:
                message = "📋 <b>Open Orders</b>\n\n<i>No open orders</i>"
                await update.message.reply_html(message)
                return

            # Pagination
            items_per_page = 10
            total_orders = len(all_orders)
            total_pages = (total_orders + items_per_page - 1) // items_per_page

            # Ensure page is within bounds
            page = max(1, min(page, total_pages))

            # Calculate slice indices
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            orders = all_orders[start_idx:end_idx]

            message = f"📋 <b>Open Orders</b>\n"
            message += f"(Page {page}/{total_pages} • Showing {len(orders)} of {total_orders})\n\n"

            for i, order in enumerate(orders, start_idx + 1):
                order_id = str(order.get('id', 'N/A'))[:8]
                symbol = order.get('symbol', 'N/A')
                side = order.get('side', 'N/A').upper()
                side_emoji = "📈" if side == "BUY" else "📉"
                qty = float(order.get('qty', 0))
                status = order.get('status', 'N/A').upper()
                created_at = order.get('created_at', 'N/A')
                if isinstance(created_at, str) and 'T' in created_at:
                    created_at = created_at.split('T')[1][:5]

                message += f"{i}. {side_emoji} <b>{symbol}</b> {side}\n"
                message += f"   ID: <code>{order_id}</code>\n"
                message += f"   Qty: {qty}\n"
                message += f"   Status: {status}\n"
                message += f"   Created: {created_at}\n\n"

            # Build pagination buttons
            keyboard = []
            nav_buttons = []

            if page > 1:
                nav_buttons.append(
                    InlineKeyboardButton("⬅️ Prev", callback_data=f"orders_page:{page - 1}")
                )

            nav_buttons.append(
                InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="cancel")
            )

            if page < total_pages:
                nav_buttons.append(
                    InlineKeyboardButton("Next ➡️", callback_data=f"orders_page:{page + 1}")
                )

            if nav_buttons:
                keyboard.append(nav_buttons)

            # Add filter help
            if symbol_filter or status_filter:
                keyboard.append([
                    InlineKeyboardButton("🔄 Clear Filters", callback_data="orders_reset")
                ])

            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

            # Determine if using callback query or regular message
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    message,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_html(message, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error in /broker_orders: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _cmd_close_position(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /close_position SYMBOL command."""
        if not await self._check_authorized(update):
            return

        if not self.broker:
            await update.message.reply_text("❌ Broker not configured")
            return

        if not context.args or len(context.args) == 0:
            await update.message.reply_text("❌ Usage: /close_position SYMBOL")
            return

        symbol = context.args[0].upper()

        try:
            # Get position details
            position = self.broker.get_position(symbol)

            if not position:
                await update.message.reply_text(f"❌ No position found for {symbol}")
                return

            qty = float(position.get('qty', 0))
            entry_price = float(position.get('avg_fill_price', 0))
            current_price = float(position.get('current_price', 0))
            pnl = float(position.get('unrealized_pl', 0))
            pnl_color = "🟢" if pnl >= 0 else "🔴"

            # Show position details and ask for confirmation
            message = f"⚠️ <b>Close Position - Confirm?</b>\n\n"
            message += f"<b>Symbol:</b> {symbol}\n"
            message += f"<b>Quantity:</b> {qty}\n"
            message += f"<b>Entry Price:</b> ${entry_price:.4f}\n"
            message += f"<b>Current Price:</b> ${current_price:.4f}\n"
            message += f"<b>Unrealized P&L:</b> {pnl_color} ${pnl:,.2f}\n\n"
            message += "Are you sure you want to close this position?"

            keyboard = [
                [
                    InlineKeyboardButton("✅ Close Position", callback_data=f"close_pos:{symbol}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_html(message, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error in /close_position: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _cmd_close_all_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /close_all_positions command."""
        if not await self._check_authorized(update):
            return

        if not self.broker:
            await update.message.reply_text("❌ Broker not configured")
            return

        try:
            positions = self.broker.get_positions()

            if not positions:
                await update.message.reply_text("ℹ️ No open positions to close")
                return

            # Show all positions and ask for confirmation
            message = f"⚠️ <b>Close All Positions - Confirm?</b>\n\n"
            message += f"<b>Total Positions:</b> {len(positions)}\n\n"

            total_pnl = 0
            for i, pos in enumerate(positions, 1):
                symbol = pos.get('symbol', 'N/A')
                qty = float(pos.get('qty', 0))
                pnl = float(pos.get('unrealized_pl', 0))
                total_pnl += pnl

                message += f"{i}. <b>{symbol}</b> (Qty: {qty})\n"

            pnl_color = "🟢" if total_pnl >= 0 else "🔴"
            message += f"\n<b>Total P&L:</b> {pnl_color} ${total_pnl:,.2f}\n\n"
            message += "Are you sure you want to close ALL positions?"

            keyboard = [
                [
                    InlineKeyboardButton("✅ Close All", callback_data="close_all_pos"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_html(message, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error in /close_all_positions: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _cmd_cancel_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel_order ORDER_ID command."""
        if not await self._check_authorized(update):
            return

        if not self.broker:
            await update.message.reply_text("❌ Broker not configured")
            return

        if not context.args or len(context.args) == 0:
            await update.message.reply_text("❌ Usage: /cancel_order ORDER_ID")
            return

        order_id = context.args[0]

        try:
            # Get order details
            order = self.broker.get_order(order_id)

            if not order:
                await update.message.reply_text(f"❌ Order not found: {order_id}")
                return

            symbol = order.get('symbol', 'N/A')
            side = order.get('side', 'N/A').upper()
            qty = float(order.get('qty', 0))
            status = order.get('status', 'N/A').upper()
            side_emoji = "📈" if side == "BUY" else "📉"

            # Show order details and ask for confirmation
            message = f"⚠️ <b>Cancel Order - Confirm?</b>\n\n"
            message += f"{side_emoji} <b>{symbol}</b>\n"
            message += f"<b>Side:</b> {side}\n"
            message += f"<b>Quantity:</b> {qty}\n"
            message += f"<b>Status:</b> {status}\n"
            message += f"<b>ID:</b> <code>{order_id}</code>\n\n"
            message += "Are you sure you want to cancel this order?"

            keyboard = [
                [
                    InlineKeyboardButton("✅ Cancel Order", callback_data=f"cancel_ord:{order_id}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_html(message, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error in /cancel_order: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _cmd_cancel_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel_orders [SYMBOL] command."""
        if not await self._check_authorized(update):
            return

        if not self.broker:
            await update.message.reply_text("❌ Broker not configured")
            return

        try:
            symbol_filter = None
            if context.args and len(context.args) > 0:
                symbol_filter = context.args[0].upper()

            orders = self.broker.get_orders(status='open', limit=100)

            if symbol_filter:
                orders = [o for o in orders if o.get('symbol', '').upper().startswith(symbol_filter)]

            if not orders:
                await update.message.reply_text("ℹ️ No open orders to cancel")
                return

            # Show orders to be cancelled and ask for confirmation
            message = f"⚠️ <b>Cancel Orders - Confirm?</b>\n\n"
            message += f"<b>Total Orders:</b> {len(orders)}\n\n"

            for i, order in enumerate(orders[:10], 1):  # Show first 10
                symbol = order.get('symbol', 'N/A')
                side = order.get('side', 'N/A').upper()
                side_emoji = "📈" if side == "BUY" else "📉"
                qty = float(order.get('qty', 0))

                message += f"{i}. {side_emoji} <b>{symbol}</b> {side} {qty}\n"

            if len(orders) > 10:
                message += f"... and {len(orders) - 10} more\n"

            message += f"\nAre you sure you want to cancel all these orders?"

            keyboard = [
                [
                    InlineKeyboardButton("✅ Cancel All", callback_data=f"cancel_ords:{symbol_filter or ''}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_html(message, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error in /cancel_orders: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _cmd_close_strategy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /close_strategy STRATEGY_NAME command.

        Closes all positions opened by a specific strategy.
        """
        if not await self._check_authorized(update):
            return

        if not self.broker or not self.database:
            await update.message.reply_text("❌ Broker or database not configured")
            return

        if not context.args or len(context.args) == 0:
            await update.message.reply_text("❌ Usage: /close_strategy STRATEGY_NAME")
            return

        strategy_name = " ".join(context.args)

        try:
            # Get all open positions for this strategy from database
            async with self.database.get_session() as session:
                positions_query = select(Position).where(
                    and_(Position.strategy.ilike(f"%{strategy_name}%"), Position.open == True)
                )
                result = await session.execute(positions_query)
                db_positions = result.scalars().all()

            if not db_positions:
                await update.message.reply_text(f"ℹ️ No open positions for strategy: {strategy_name}")
                return

            # Get current position details from broker
            broker_positions = {p.get('symbol'): p for p in self.broker.get_positions()}

            positions_to_close = []
            for db_pos in db_positions:
                if db_pos.symbol in broker_positions:
                    positions_to_close.append(db_pos)

            if not positions_to_close:
                await update.message.reply_text(f"ℹ️ No open positions in broker for strategy: {strategy_name}")
                return

            # Show positions and ask for confirmation
            message = f"⚠️ <b>Close Strategy Positions - Confirm?</b>\n\n"
            message += f"<b>Strategy:</b> {strategy_name}\n"
            message += f"<b>Total Positions:</b> {len(positions_to_close)}\n\n"

            total_pnl = 0
            for i, pos in enumerate(positions_to_close, 1):
                broker_pos = broker_positions.get(pos.symbol, {})
                qty = float(broker_pos.get('qty', 0))
                pnl = float(broker_pos.get('unrealized_pl', 0))
                total_pnl += pnl

                pnl_color = "🟢" if pnl >= 0 else "🔴"
                message += f"{i}. <b>{pos.symbol}</b> (Qty: {qty}) {pnl_color} ${pnl:,.2f}\n"

            pnl_color = "🟢" if total_pnl >= 0 else "🔴"
            message += f"\n<b>Total P&L:</b> {pnl_color} ${total_pnl:,.2f}\n\n"
            message += "Are you sure you want to close ALL positions from this strategy?"

            keyboard = [
                [
                    InlineKeyboardButton("✅ Close All", callback_data=f"close_strat:{strategy_name}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_html(message, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error in /close_strategy: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _cmd_cancel_strategy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel_strategy STRATEGY_NAME command.

        Cancels all pending orders for a specific strategy's symbols.
        """
        if not await self._check_authorized(update):
            return

        if not self.broker or not self.database:
            await update.message.reply_text("❌ Broker or database not configured")
            return

        if not context.args or len(context.args) == 0:
            await update.message.reply_text("❌ Usage: /cancel_strategy STRATEGY_NAME")
            return

        strategy_name = " ".join(context.args)

        try:
            # Get all open positions for this strategy from database
            async with self.database.get_session() as session:
                positions_query = select(Position).where(
                    and_(Position.strategy.ilike(f"%{strategy_name}%"), Position.open == True)
                )
                result = await session.execute(positions_query)
                db_positions = result.scalars().all()

            if not db_positions:
                await update.message.reply_text(f"ℹ️ No open positions for strategy: {strategy_name}")
                return

            # Get symbols for this strategy
            strategy_symbols = set(pos.symbol for pos in db_positions)

            # Get all open orders from broker
            all_orders = self.broker.get_orders(status='open', limit=100)

            # Filter orders to only those for strategy symbols
            orders_to_cancel = [o for o in all_orders if o.get('symbol', '').upper() in strategy_symbols]

            if not orders_to_cancel:
                await update.message.reply_text(f"ℹ️ No open orders for strategy: {strategy_name}")
                return

            # Show orders to be cancelled and ask for confirmation
            message = f"⚠️ <b>Cancel Strategy Orders - Confirm?</b>\n\n"
            message += f"<b>Strategy:</b> {strategy_name}\n"
            message += f"<b>Total Orders:</b> {len(orders_to_cancel)}\n"
            message += f"<b>Symbols:</b> {', '.join(sorted(strategy_symbols))}\n\n"

            for i, order in enumerate(orders_to_cancel[:10], 1):  # Show first 10
                symbol = order.get('symbol', 'N/A')
                side = order.get('side', 'N/A').upper()
                side_emoji = "📈" if side == "BUY" else "📉"
                qty = float(order.get('qty', 0))

                message += f"{i}. {side_emoji} <b>{symbol}</b> {side} {qty}\n"

            if len(orders_to_cancel) > 10:
                message += f"... and {len(orders_to_cancel) - 10} more\n"

            message += f"\nAre you sure you want to cancel ALL orders for this strategy?"

            keyboard = [
                [
                    InlineKeyboardButton("✅ Cancel All", callback_data=f"cancel_strat:{strategy_name}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_html(message, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error in /cancel_strategy: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _handle_trades_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trades button callbacks for quick filtering."""
        query = update.callback_query
        await query.answer()

        if not await self._check_authorized(update):
            return

        try:
            callback_data = query.data

            # Parse callback to determine filter
            if callback_data == "trades_open":
                context.args = ["open"]
            elif callback_data == "trades_closed":
                context.args = ["closed"]
            elif callback_data == "trades_all":
                context.args = []
            elif callback_data.startswith("trades_strat_"):
                strategy_name = callback_data.replace("trades_strat_", "")
                context.args = [strategy_name]
            else:
                return

            # Re-execute the trades command with the new filter
            await self._cmd_trades(update, context)

        except Exception as e:
            logger.error(f"Error in trades callback: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def _handle_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle confirmation callbacks from inline keyboards."""
        if not await self._check_authorized(update):
            return

        query = update.callback_query
        await query.answer()

        try:
            action = query.data

            # Handle close position
            if action.startswith("close_pos:"):
                symbol = action.split(":")[1]
                result = self.broker.close_position(symbol)
                if result:
                    await query.edit_message_text(f"✅ Position closed: {symbol}")
                    logger.info(f"Position closed via Telegram: {symbol}")
                else:
                    await query.edit_message_text(f"❌ Failed to close position: {symbol}")
                return

            # Handle close all positions
            if action == "close_all_pos":
                positions = self.broker.get_positions()
                closed_count = 0
                failed_symbols = []

                for pos in positions:
                    symbol = pos.get('symbol')
                    if self.broker.close_position(symbol):
                        closed_count += 1
                    else:
                        failed_symbols.append(symbol)

                message = f"✅ Closed {closed_count} positions"
                if failed_symbols:
                    message += f"\n❌ Failed: {', '.join(failed_symbols)}"
                await query.edit_message_text(message)
                logger.info(f"Closed {closed_count} positions via Telegram")
                return

            # Handle cancel order
            if action.startswith("cancel_ord:"):
                order_id = action.split(":")[1]
                result = self.broker.cancel_order(order_id)
                if result:
                    await query.edit_message_text(f"✅ Order cancelled: {order_id}")
                    logger.info(f"Order cancelled via Telegram: {order_id}")
                else:
                    await query.edit_message_text(f"❌ Failed to cancel order: {order_id}")
                return

            # Handle cancel all orders
            if action.startswith("cancel_ords:"):
                symbol_filter = action.split(":")[1] or None
                cancelled_ids = self.broker.cancel_all_orders(symbol=symbol_filter)

                if cancelled_ids:
                    await query.edit_message_text(
                        f"✅ Cancelled {len(cancelled_ids)} orders"
                        + (f" for {symbol_filter}" if symbol_filter else "")
                    )
                    logger.info(f"Cancelled {len(cancelled_ids)} orders via Telegram")
                else:
                    await query.edit_message_text("ℹ️ No orders were cancelled")
                return

            # Handle close strategy positions
            if action.startswith("close_strat:"):
                strategy_name = action.split(":", 1)[1]

                # Get all open positions for this strategy from database
                try:
                    async with self.database.get_session() as session:
                        positions_query = select(Position).where(
                            and_(Position.strategy.ilike(f"%{strategy_name}%"), Position.open == True)
                        )
                        result = await session.execute(positions_query)
                        db_positions = result.scalars().all()
                except Exception as e:
                    await query.edit_message_text(f"❌ Database error: {str(e)}")
                    return

                # Get current positions from broker
                broker_positions = {p.get('symbol'): p for p in self.broker.get_positions()}
                closed_count = 0
                failed_symbols = []

                for pos in db_positions:
                    if pos.symbol in broker_positions:
                        if self.broker.close_position(pos.symbol):
                            closed_count += 1
                        else:
                            failed_symbols.append(pos.symbol)

                message = f"✅ Closed {closed_count} positions from strategy '{strategy_name}'"
                if failed_symbols:
                    message += f"\n❌ Failed: {', '.join(failed_symbols)}"
                await query.edit_message_text(message)
                logger.info(f"Closed {closed_count} positions from strategy '{strategy_name}' via Telegram")
                return

            # Handle cancel strategy orders
            if action.startswith("cancel_strat:"):
                strategy_name = action.split(":", 1)[1]

                # Get symbols for this strategy from database
                try:
                    async with self.database.get_session() as session:
                        positions_query = select(Position).where(
                            and_(Position.strategy.ilike(f"%{strategy_name}%"), Position.open == True)
                        )
                        result = await session.execute(positions_query)
                        db_positions = result.scalars().all()
                except Exception as e:
                    await query.edit_message_text(f"❌ Database error: {str(e)}")
                    return

                strategy_symbols = set(pos.symbol for pos in db_positions)

                # Get all open orders and filter by strategy symbols
                all_orders = self.broker.get_orders(status='open', limit=100)
                orders_to_cancel = [o for o in all_orders if o.get('symbol', '').upper() in strategy_symbols]

                # Cancel the orders
                cancelled_ids = []
                for order in orders_to_cancel:
                    try:
                        if self.broker.cancel_order(order.get('id')):
                            cancelled_ids.append(order.get('id'))
                    except Exception as e:
                        logger.warning(f"Failed to cancel order {order.get('id')}: {e}")

                message = f"✅ Cancelled {len(cancelled_ids)} orders from strategy '{strategy_name}'"
                if len(orders_to_cancel) > len(cancelled_ids):
                    message += f"\n⚠️ {len(orders_to_cancel) - len(cancelled_ids)} orders failed to cancel"
                await query.edit_message_text(message)
                logger.info(f"Cancelled {len(cancelled_ids)} orders from strategy '{strategy_name}' via Telegram")
                return

            # Handle orders pagination
            if action.startswith("orders_page:"):
                page = int(action.split(":")[1])
                context.user_data = context.user_data or {}
                context.user_data['orders_page'] = page
                await self._cmd_broker_orders(update, context)
                return

            # Handle orders reset filters
            if action == "orders_reset":
                context.args = []
                context.user_data = context.user_data or {}
                context.user_data['orders_page'] = 1
                await self._cmd_broker_orders(update, context)
                return

            # Handle cancel
            if action == "cancel":
                await query.edit_message_text("❌ Cancelled")
                return

        except Exception as e:
            logger.error(f"Error in confirmation handler: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def start(self) -> None:
        """Start the bot in webhook or polling mode (background task).

        Tries webhook mode if webhook_url is configured, falls back to polling if it fails.
        """
        if not self.application:
            return

        try:
            await self.application.initialize()
            await self.application.start()

            # Try webhook mode if configured
            if self.webhook_url:
                try:
                    logger.info(f"Starting Telegram bot in webhook mode on port {self.webhook_port}...")
                    await self.application.updater.start_webhook(
                        listen="0.0.0.0",
                        port=self.webhook_port,
                        url_path=f"webhook/{self.token}",
                        secret_token=self.webhook_secret or None,
                        webhook_url=f"{self.webhook_url}/webhook/{self.token}",
                        allowed_updates=Update.ALL_TYPES,
                    )
                    logger.info(f"✅ Telegram webhook active at {self.webhook_url}/webhook/{self.token}")
                    return
                except Exception as e:
                    logger.warning(f"Webhook setup failed: {e} — falling back to polling mode")

            # Polling mode (default or fallback)
            logger.info("Starting Telegram bot in polling mode...")
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

            # Dispose database connection if initialized
            if self.database:
                await self.database.dispose()

            logger.info("Telegram bot stopped")
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {e}")
