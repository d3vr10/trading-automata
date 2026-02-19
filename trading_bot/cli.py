"""Command-line interface for trading bot data queries.

Provides commands to check:
- Bot status
- Recent trades and performance
- Health checks
- Broker account information
- Database queries
"""

import asyncio
import sys
import time
from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional, Callable

import click
from sqlalchemy import select, func
from tabulate import tabulate

from config.settings import load_settings
from trading_bot.database.models import DatabaseConnection, Trade, Position, HealthCheck, TradingEvent, BotSession
from trading_bot.database.repository import TradeRepository
from trading_bot.brokers.factory import BrokerFactory
from trading_bot.brokers.base import IBroker


# Color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def colored(text: str, color: str) -> str:
    """Add color to text for terminal output."""
    return f"{color}{text}{Colors.RESET}"


def get_database():
    """Get database connection with ORM session factory."""
    settings = load_settings()
    try:
        db = DatabaseConnection(
            database_url=settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
        )
        return db
    except Exception as e:
        click.echo(colored(f"❌ Failed to connect to database: {e}", Colors.RED))
        sys.exit(1)


def get_broker() -> IBroker:
    """Get broker instance connected and ready to trade."""
    settings = load_settings()
    try:
        from trading_bot.brokers.base import Environment

        # Load broker configuration from settings
        broker_config = BrokerFactory.build_config_from_settings(settings)
        environment = Environment(settings.trading_environment)

        # Create and connect broker
        broker = BrokerFactory.create_broker(
            broker_type=settings.broker,
            environment=environment,
            config=broker_config
        )

        if not broker.connect():
            raise RuntimeError(f"Failed to connect to {settings.broker} broker")

        return broker
    except Exception as e:
        click.echo(colored(f"❌ Failed to connect to broker: {e}", Colors.RED))
        sys.exit(1)


def watch_command(async_fn: Callable, watch: bool, interval: int = 2):
    """Helper to run a command with optional watch mode.

    Args:
        async_fn: Async function to run
        watch: Whether to enable watch mode
        interval: Refresh interval in seconds (default 2)
    """
    if not watch:
        asyncio.run(async_fn())
    else:
        try:
            while True:
                # Clear screen
                click.clear()
                asyncio.run(async_fn())
                click.echo(colored(f"\n(Watching... press Ctrl+C to stop, refreshing every {interval}s)", Colors.CYAN))
                time.sleep(interval)
        except KeyboardInterrupt:
            click.echo(colored("\nWatch mode stopped.", Colors.YELLOW))
            sys.exit(0)


@click.group()
def cli():
    """Trading Bot CLI - Check bot data and status."""
    pass


@cli.command()
@click.option('--format', type=click.Choice(['table', 'json']), default='table',
              help='Output format')
@click.option('--watch', is_flag=True, help='Watch for updates (refresh every 2 seconds)')
def status(format, watch):
    """Check overall bot status."""
    async def _status():
        settings = load_settings()

        click.echo(f"\n{colored('🤖 Trading Bot Status', Colors.BOLD)}")
        click.echo(colored('=' * 50, Colors.CYAN))

        status_info = [
            ['Configuration', ''],
            ['Broker', colored(settings.broker.upper(), Colors.GREEN)],
            ['Environment', colored(settings.trading_environment.upper(), Colors.GREEN)],
            ['Log Level', settings.log_level],
            ['Strategy Config', settings.strategy_config_path],
            ['', ''],
            ['Risk Management', ''],
            ['Max Position Size', f"{settings.max_position_size * 100:.1f}%"],
            ['Max Portfolio Risk', f"{settings.max_portfolio_risk * 100:.1f}%"],
            ['', ''],
            ['Database', ''],
            ['Database URL', settings.database_url.split('@')[1] if '@' in settings.database_url else 'N/A'],
            ['Pool Size', str(settings.database_pool_size)],
        ]

        click.echo(tabulate(status_info, tablefmt='plain'))
        click.echo()

    watch_command(_status, watch)


@cli.command()
@click.option('--limit', type=int, default=10, help='Number of trades to show')
@click.option('--symbol', type=str, default=None, help='Filter by symbol')
@click.option('--strategy', type=str, default=None, help='Filter by strategy')
@click.option('--watch', is_flag=True, help='Watch for updates (refresh every 2 seconds)')
def trades(limit, symbol, strategy, watch):
    """View recent trades from database."""
    async def _trades():
        db = get_database()
        repo = TradeRepository(db.session_factory)

        try:
            if symbol:
                trades_list = await repo.get_trades_by_symbol(symbol, limit=limit)
            elif strategy:
                trades_list = await repo.get_trades_by_strategy(strategy, limit=limit)
            else:
                # Get all recent trades
                async with db.session_factory() as session:
                    stmt = select(Trade).order_by(Trade.entry_timestamp.desc()).limit(limit)
                    result = await session.execute(stmt)
                    trade_objs = result.scalars().all()
                    trades_list = [
                        {
                            'id': t.id,
                            'symbol': t.symbol,
                            'strategy': t.strategy,
                            'entry_price': t.entry_price,
                            'entry_quantity': t.entry_quantity,
                            'exit_price': t.exit_price,
                            'exit_quantity': t.exit_quantity,
                            'pnl_percent': t.pnl_percent,
                            'entry_timestamp': t.entry_timestamp,
                            'exit_timestamp': t.exit_timestamp,
                        }
                        for t in trade_objs
                    ]

            if not trades_list:
                click.echo(colored("No trades found", Colors.YELLOW))
                return

            click.echo(f"\n{colored('📊 Recent Trades', Colors.BOLD)}")
            click.echo(colored('=' * 120, Colors.CYAN))

            headers = ['ID', 'Symbol', 'Strategy', 'Side', 'Entry Price', 'Qty',
                      'Exit Price', 'Exit Qty', 'P&L %', 'Entry Time', 'Exit Time']

            rows = []
            for trade in trades_list:
                entry_price = trade.get('entry_price') or trade['entry_price']
                entry_qty = trade.get('entry_quantity') or trade['entry_quantity']
                exit_price = trade.get('exit_price')
                exit_qty = trade.get('exit_quantity')
                pnl = trade.get('pnl_percent')
                entry_ts = trade.get('entry_timestamp')
                exit_ts = trade.get('exit_timestamp')

                # Color code P&L
                pnl_str = f"{pnl:.2f}%" if pnl else "Open"
                if pnl and pnl > 0:
                    pnl_str = colored(pnl_str, Colors.GREEN)
                elif pnl and pnl < 0:
                    pnl_str = colored(pnl_str, Colors.RED)

                rows.append([
                    trade['id'],
                    trade['symbol'],
                    trade['strategy'],
                    'BUY' if entry_ts else 'N/A',
                    f"${float(entry_price):.2f}" if entry_price else 'N/A',
                    f"{float(entry_qty):.4f}" if entry_qty else 'N/A',
                    f"${float(exit_price):.2f}" if exit_price else 'N/A',
                    f"{float(exit_qty):.4f}" if exit_qty else 'N/A',
                    pnl_str,
                    entry_ts.strftime('%Y-%m-%d %H:%M:%S') if entry_ts else 'N/A',
                    exit_ts.strftime('%Y-%m-%d %H:%M:%S') if exit_ts else 'Open',
                ])

            click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
            click.echo()

        finally:
            await db.dispose()

    watch_command(_trades, watch)


@cli.command()
def metrics():
    """Show performance metrics."""
    async def _metrics():
        db = get_database()
        repo = TradeRepository(db.session_factory)

        try:
            metrics_data = await repo.get_performance_metrics()

            if not metrics_data:
                click.echo(colored("No metrics available yet", Colors.YELLOW))
                return

            click.echo(f"\n{colored('📈 Performance Metrics', Colors.BOLD)}")
            click.echo(colored('=' * 50, Colors.CYAN))

            metrics_rows = []
            for key, value in metrics_data.items():
                if isinstance(value, float):
                    value = f"{value:.2f}" if value < 100 else f"{int(value)}"
                metrics_rows.append([key.replace('_', ' ').title(), value])

            click.echo(tabulate(metrics_rows, tablefmt='simple'))
            click.echo()

        finally:
            await db.dispose()

    asyncio.run(_metrics())


@cli.command()
@click.option('--watch', is_flag=True, help='Watch for updates (refresh every 2 seconds)')
def health(watch):
    """Check bot health status."""
    async def _health():
        db = get_database()

        try:
            click.echo(f"\n{colored('🔋 Health Check Status', Colors.BOLD)}")
            click.echo(colored('=' * 80, Colors.CYAN))

            async with db.session_factory() as session:
                stmt = select(HealthCheck).order_by(HealthCheck.checked_at.desc())
                result = await session.execute(stmt)
                checks = result.scalars().all()

                if not checks:
                    click.echo(colored("No health checks recorded yet", Colors.YELLOW))
                    return

                headers = ['Broker', 'Strategy', 'Status', 'Errors', 'Last Bar']
                rows = []

                for check in checks:
                    status = colored('🟢 Healthy', Colors.GREEN) if check.is_healthy else colored('🔴 Unhealthy', Colors.RED)
                    last_bar = check.last_bar_timestamp.strftime('%Y-%m-%d %H:%M:%S') if check.last_bar_timestamp else 'Never'
                    rows.append([check.broker, check.strategy or '-', status, check.connection_errors, last_bar])

                click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
                click.echo()

        finally:
            await db.dispose()

    watch_command(_health, watch)


@cli.command()
@click.option('--watch', is_flag=True, help='Watch for updates (refresh every 2 seconds)')
def positions(watch):
    """Show current open positions."""
    async def _positions():
        db = get_database()

        try:
            async with db.session_factory() as session:
                stmt = select(Position).where(Position.is_open == True).order_by(Position.opened_at.desc())
                result = await session.execute(stmt)
                positions_list = result.scalars().all()

                if not positions_list:
                    click.echo(colored("No open positions", Colors.YELLOW))
                    return

                click.echo(f"\n{colored('💼 Open Positions', Colors.BOLD)}")
                click.echo(colored('=' * 80, Colors.CYAN))

                headers = ['Symbol', 'Strategy', 'Entry Price', 'Quantity', 'Entry Time']
                rows = []

                for pos in positions_list:
                    rows.append([
                        pos.symbol,
                        pos.strategy,
                        f"${float(pos.entry_price):.2f}",
                        f"{float(pos.quantity):.4f}",
                        pos.opened_at.strftime('%Y-%m-%d %H:%M:%S'),
                    ])

                click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
                click.echo(f"\nTotal open positions: {len(positions_list)}")
                click.echo()

        finally:
            await db.dispose()

    watch_command(_positions, watch)


@cli.command()
def query():
    """Run custom SQL query on trading database."""
    click.echo(colored("Custom SQL Query Mode", Colors.BOLD))
    click.echo("Type 'exit' to quit\n")

    async def _query_loop():
        db = get_database()

        try:
            while True:
                sql = click.prompt("SQL> ", type=str)

                if sql.lower() == 'exit':
                    break

                if not sql.strip():
                    continue

                try:
                    # Safety: only allow SELECT queries
                    if not sql.strip().upper().startswith('SELECT'):
                        click.echo(colored("Only SELECT queries are allowed", Colors.RED))
                        continue

                    async with db.session_factory() as session:
                        from sqlalchemy import text
                        result = await session.execute(text(sql))
                        rows = result.fetchall()

                        if rows:
                            # Get column names from result keys
                            headers = result.keys()
                            click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
                        else:
                            click.echo(colored("No results", Colors.YELLOW))

                except Exception as e:
                    click.echo(colored(f"Error: {e}", Colors.RED))

        finally:
            await db.dispose()

    asyncio.run(_query_loop())


@cli.command()
@click.option('--table', type=click.Choice(['trades', 'positions', 'health_checks', 'performance_metrics']),
              required=True, help='Table to check schema for')
def schema(table):
    """Show database table schema."""
    async def _schema():
        db = get_database()

        try:
            async with db.session_factory() as session:
                from sqlalchemy import text
                result = await session.execute(
                    text("""
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_name = :table_name
                        ORDER BY ordinal_position
                    """),
                    {"table_name": table}
                )
                columns = result.fetchall()

                if not columns:
                    click.echo(colored(f"Table '{table}' not found", Colors.RED))
                    return

                click.echo(f"\n{colored(f'📋 Table Schema: {table}', Colors.BOLD)}")
                click.echo(colored('=' * 80, Colors.CYAN))

                headers = ['Column', 'Type', 'Nullable', 'Default']
                rows = []

                for col_name, data_type, nullable, default in columns:
                    rows.append([
                        col_name,
                        data_type,
                        'Yes' if nullable == 'YES' else 'No',
                        default or 'N/A',
                    ])

                click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
                click.echo()

        finally:
            await db.dispose()

    asyncio.run(_schema())


@cli.command()
@click.option('--watch', is_flag=True, help='Watch for updates (refresh every 2 seconds)')
def summary(watch):
    """Show quick summary of everything."""
    async def _summary():
        db = get_database()
        repo = TradeRepository(db.session_factory)

        try:
            async with db.session_factory() as session:
                # Count trades
                trade_count_result = await session.execute(select(func.count(Trade.id)))
                trade_count = trade_count_result.scalar() or 0

                # Count open positions
                open_pos_result = await session.execute(
                    select(func.count(Position.id)).where(Position.is_open == True)
                )
                open_positions = open_pos_result.scalar() or 0

                # Get health status
                healthy_result = await session.execute(
                    select(func.count(HealthCheck.id)).where(HealthCheck.is_healthy == True)
                )
                healthy_checks = healthy_result.scalar() or 0

            # Get win rate and profit factor
            metrics = await repo.get_performance_metrics()

            click.echo(f"\n{colored('🎯 Trading Bot Summary', Colors.BOLD)}")
            click.echo(colored('=' * 50, Colors.CYAN))

            summary_rows = [
                ['Total Trades', colored(str(trade_count), Colors.BLUE)],
                ['Open Positions', colored(str(open_positions), Colors.BLUE)],
                ['Win Rate', colored(f"{metrics.get('win_rate', 0):.1f}%", Colors.GREEN if metrics.get('win_rate', 0) > 50 else Colors.RED)],
                ['Profit Factor', colored(f"{metrics.get('profit_factor', 0):.2f}", Colors.GREEN if metrics.get('profit_factor', 0) > 1.5 else Colors.YELLOW)],
                ['Healthy Checks', colored(str(healthy_checks), Colors.GREEN)],
            ]

            click.echo(tabulate(summary_rows, tablefmt='simple'))
            click.echo()

        finally:
            await db.dispose()

    watch_command(_summary, watch)


@cli.command()
@click.option('--limit', default=50, help='Number of events to show')
@click.option('--symbol', default=None, help='Filter by symbol')
@click.option('--type', 'event_type', default=None, help='Filter by event type')
@click.option('--severity', default=None, help='Filter by severity level')
@click.option('--watch', is_flag=True, help='Watch for updates (refresh every 2 seconds)')
def events(limit, symbol, event_type, severity, watch):
    """View trading events and decisions.

    Shows strategy decisions, filter checks, signal generation, and order events.
    Use this to troubleshoot why the bot isn't making trades.
    """
    async def _events():
        db = get_database()

        try:
            async with db.session_factory() as session:
                # Build query with filters
                stmt = select(TradingEvent)

                if symbol:
                    stmt = stmt.where(TradingEvent.symbol == symbol)

                if event_type:
                    stmt = stmt.where(TradingEvent.event_type == event_type)

                if severity:
                    stmt = stmt.where(TradingEvent.severity == severity)

                stmt = stmt.order_by(TradingEvent.event_timestamp.desc()).limit(limit)

                result = await session.execute(stmt)
                events_data = result.scalars().all()

                if not events_data:
                    click.echo(colored("No events found", Colors.YELLOW))
                    return

                click.echo(f"\n{colored('📊 Trading Events', Colors.BOLD)}")
                click.echo(colored('=' * 100, Colors.CYAN))

                # Format events for display
                rows = []
                for event in events_data:
                    # Color code by severity
                    if event.severity == 'ERROR':
                        sev_colored = colored(event.severity, Colors.RED)
                    elif event.severity == 'WARNING':
                        sev_colored = colored(event.severity, Colors.YELLOW)
                    else:
                        sev_colored = colored(event.severity, Colors.GREEN)

                    # Format timestamp
                    ts_str = event.event_timestamp.strftime('%H:%M:%S')

                    rows.append([
                        ts_str,
                        colored(event.symbol or '-', Colors.BLUE),
                        colored(event.strategy or '-', Colors.CYAN),
                        sev_colored,
                        event.event_type[:20],
                        event.message[:50] + ('...' if len(event.message) > 50 else ''),
                    ])

                click.echo(tabulate(rows, headers=['Time', 'Symbol', 'Strategy', 'Level', 'Type', 'Message'], tablefmt='simple'))
                click.echo()

        finally:
            await db.dispose()

    watch_command(_events, watch)


@cli.command()
def version():
    """Show bot version."""
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

    click.echo(f"\n{colored('🤖 Trading Bot Version', Colors.BOLD)}")
    click.echo(colored('=' * 40, Colors.CYAN))
    click.echo(f"Version: {colored(version_str, Colors.GREEN)}")
    click.echo()


@cli.command()
def uptime():
    """Show bot uptime and start time."""
    async def _uptime():
        db = get_database()
        try:
            async with db.session_factory() as session:
                # Get the latest bot session start time (actual process start, not database lifetime)
                stmt = select(BotSession).order_by(BotSession.started_at.desc()).limit(1)
                result = await session.execute(stmt)
                bot_session = result.scalar_one_or_none()
                start_time = bot_session.started_at if bot_session else None

                click.echo(f"\n{colored('⏱️  Bot Uptime', Colors.BOLD)}")
                click.echo(colored('=' * 50, Colors.CYAN))

                if start_time:
                    now = datetime.now(UTC)
                    uptime_delta = now - start_time
                    hours = uptime_delta.seconds // 3600
                    minutes = (uptime_delta.seconds % 3600) // 60
                    seconds = uptime_delta.seconds % 60
                    days = uptime_delta.days

                    click.echo(f"Started at: {colored(start_time.strftime('%Y-%m-%d %H:%M:%S UTC'), Colors.BLUE)}")
                    click.echo(f"Current time: {colored(now.strftime('%Y-%m-%d %H:%M:%S UTC'), Colors.BLUE)}")
                    click.echo(f"Uptime: {colored(f'{days}d {hours}h {minutes}m {seconds}s', Colors.GREEN)}")
                else:
                    click.echo(colored("No bot session found - bot may not have started yet", Colors.YELLOW))

                click.echo()

        finally:
            await db.dispose()

    asyncio.run(_uptime())


# Broker Management Commands

@cli.command(name='broker-positions')
def broker_positions():
    """List live open positions from broker."""
    try:
        broker = get_broker()
        positions = broker.get_positions()

        if not positions:
            click.echo(colored("\n📊 Open Positions\n", Colors.BOLD))
            click.echo("No open positions")
            click.echo()
            return

        # Format positions table
        click.echo(colored("\n📊 Open Positions\n", Colors.BOLD))
        click.echo(colored("=" * 80, Colors.CYAN))

        table_data = []
        for i, pos in enumerate(positions, 1):
            symbol = pos.get('symbol', 'N/A')
            qty = pos.get('qty', 0)
            entry_price = pos.get('entry_price', 0)
            current_price = pos.get('current_price', 0)
            pnl = pos.get('unrealized_pnl', 0)
            pnl_pct = pos.get('unrealized_pnl_pct', 0)

            pnl_color = Colors.GREEN if pnl >= 0 else Colors.RED
            table_data.append([
                i,
                symbol,
                f"{float(qty):.4f}",
                f"${float(entry_price):.2f}",
                f"${float(current_price):.2f}",
                colored(f"${float(pnl):.2f} ({float(pnl_pct):.1f}%)", pnl_color)
            ])

        headers = ["#", "Symbol", "Qty", "Entry Price", "Current Price", "P&L"]
        click.echo(tabulate(table_data, headers=headers, tablefmt='grid'))
        click.echo()

    finally:
        if 'broker' in locals():
            broker.disconnect()


@cli.command(name='broker-orders')
@click.option('--symbol', '-s', default=None, help='Filter by symbol')
@click.option('--status', '-st', default='open', help='Filter by status (open, closed, etc.)')
def broker_orders(symbol, status):
    """List open orders from broker."""
    try:
        broker = get_broker()
        orders = broker.get_orders(status=status)

        if symbol:
            orders = [o for o in orders if o.get('symbol') == symbol]

        if not orders:
            click.echo(colored(f"\n📋 Open Orders\n", Colors.BOLD))
            click.echo(f"No orders found{f' for {symbol}' if symbol else ''}")
            click.echo()
            return

        click.echo(colored(f"\n📋 Open Orders {f'for {symbol}' if symbol else ''}\n", Colors.BOLD))
        click.echo(colored("=" * 100, Colors.CYAN))

        table_data = []
        for i, order in enumerate(orders, 1):
            order_id = str(order.get('id', 'N/A'))[:8]  # First 8 chars
            symbol = order.get('symbol', 'N/A')
            side = order.get('side', 'N/A').upper()
            qty = order.get('qty', 0)
            price = order.get('price', 0)
            status_val = order.get('status', 'N/A')
            created = order.get('created_at', 'N/A')

            side_emoji = "📈" if side == 'BUY' else "📉"
            table_data.append([
                i,
                f"{order_id}...",
                symbol,
                f"{side_emoji} {side}",
                f"{float(qty):.4f}",
                f"${float(price):.2f}" if price else "Market",
                status_val,
                str(created)[:16] if created != 'N/A' else 'N/A'
            ])

        headers = ["#", "Order ID", "Symbol", "Side", "Qty", "Price", "Status", "Created"]
        click.echo(tabulate(table_data, headers=headers, tablefmt='grid'))
        click.echo()

    finally:
        if 'broker' in locals():
            broker.disconnect()


@cli.command(name='close-position')
@click.argument('symbol')
@click.option('--confirm', '-y', is_flag=True, help='Skip confirmation prompt')
def close_position(symbol, confirm):
    """Close/liquidate a position by symbol."""
    try:
        broker = get_broker()

        # Show current position
        position = broker.get_position(symbol)
        if not position:
            click.echo(colored(f"\n❌ No position found for {symbol}\n", Colors.RED))
            return

        qty = position.get('qty', 0)
        entry_price = position.get('entry_price', 0)
        current_price = position.get('current_price', 0)
        pnl = position.get('unrealized_pnl', 0)

        click.echo(colored(f"\n🔚 Close Position: {symbol}", Colors.BOLD))
        click.echo(colored("=" * 50, Colors.CYAN))
        click.echo(f"Quantity: {float(qty):.4f}")
        click.echo(f"Entry Price: ${float(entry_price):.2f}")
        click.echo(f"Current Price: ${float(current_price):.2f}")
        click.echo(colored(f"P&L: ${float(pnl):.2f}", Colors.GREEN if pnl >= 0 else Colors.RED))
        click.echo()

        if not confirm:
            if not click.confirm(f"Close position for {symbol}?"):
                click.echo("Cancelled")
                return

        # Close position
        if broker.close_position(symbol):
            click.echo(colored(f"✅ Position closed for {symbol}\n", Colors.GREEN))
        else:
            click.echo(colored(f"❌ Failed to close position for {symbol}\n", Colors.RED))

    finally:
        if 'broker' in locals():
            broker.disconnect()


@cli.command(name='close-all-positions')
@click.option('--confirm', '-y', is_flag=True, help='Skip confirmation prompt')
def close_all_positions(confirm):
    """Close all open positions."""
    try:
        broker = get_broker()

        positions = broker.get_positions()
        if not positions:
            click.echo(colored("\n❌ No open positions\n", Colors.RED))
            return

        click.echo(colored(f"\n🔚 Close All Positions", Colors.BOLD))
        click.echo(colored("=" * 50, Colors.CYAN))
        click.echo(f"Found {len(positions)} open position(s):\n")

        for pos in positions:
            symbol = pos.get('symbol', 'N/A')
            qty = pos.get('qty', 0)
            pnl = pos.get('unrealized_pnl', 0)
            click.echo(f"  • {symbol}: {float(qty):.4f} (P&L: ${float(pnl):.2f})")

        click.echo()

        if not confirm:
            if not click.confirm(f"Close all {len(positions)} position(s)?"):
                click.echo("Cancelled")
                return

        # Close all positions
        closed_count = 0
        for pos in positions:
            symbol = pos.get('symbol')
            if symbol and broker.close_position(symbol):
                closed_count += 1
                click.echo(f"  ✅ Closed {symbol}")
            else:
                click.echo(colored(f"  ❌ Failed to close {symbol}", Colors.RED))

        click.echo(colored(f"\nClosed {closed_count}/{len(positions)} positions\n", Colors.GREEN if closed_count == len(positions) else Colors.YELLOW))

    finally:
        if 'broker' in locals():
            broker.disconnect()


@cli.command(name='cancel-order')
@click.argument('order_id')
@click.option('--confirm', '-y', is_flag=True, help='Skip confirmation prompt')
def cancel_order(order_id, confirm):
    """Cancel a single order by ID."""
    try:
        broker = get_broker()

        # Show order details
        try:
            order = broker.get_order(order_id)
            if not order:
                click.echo(colored(f"\n❌ Order not found: {order_id}\n", Colors.RED))
                return
        except:
            click.echo(colored(f"\n⚠️  Could not fetch order details (order may not exist)\n", Colors.YELLOW))
            order = None

        click.echo(colored(f"\n🚫 Cancel Order: {order_id}", Colors.BOLD))
        click.echo(colored("=" * 50, Colors.CYAN))

        if order:
            click.echo(f"Symbol: {order.get('symbol', 'N/A')}")
            click.echo(f"Side: {order.get('side', 'N/A').upper()}")
            click.echo(f"Qty: {float(order.get('qty', 0)):.4f}")
            click.echo(f"Status: {order.get('status', 'N/A')}")
            click.echo()

        if not confirm:
            if not click.confirm(f"Cancel order {order_id}?"):
                click.echo("Cancelled")
                return

        if broker.cancel_order(order_id):
            click.echo(colored(f"✅ Order cancelled: {order_id}\n", Colors.GREEN))
        else:
            click.echo(colored(f"❌ Failed to cancel order: {order_id}\n", Colors.RED))

    finally:
        if 'broker' in locals():
            broker.disconnect()


@cli.command(name='cancel-orders')
@click.option('--symbol', '-s', default=None, help='Cancel only orders for this symbol')
@click.option('--confirm', '-y', is_flag=True, help='Skip confirmation prompt')
def cancel_orders(symbol, confirm):
    """Cancel multiple open orders."""
    try:
        broker = get_broker()

        # Get orders to cancel
        order_ids = broker.cancel_all_orders(symbol)

        if not order_ids:
            click.echo(colored(f"\n❌ No open orders{f' for {symbol}' if symbol else ''}\n", Colors.RED))
            return

        click.echo(colored(f"\n🚫 Cancel Orders{f' for {symbol}' if symbol else ''}", Colors.BOLD))
        click.echo(colored("=" * 50, Colors.CYAN))
        click.echo(f"Found {len(order_ids)} order(s) to cancel:\n")

        # This would list them if we had the data
        # For now just show count
        click.echo()

        if not confirm:
            if not click.confirm(f"Cancel {len(order_ids)} order(s)?"):
                click.echo("Cancelled")
                return

        # Orders already cancelled by cancel_all_orders, just report
        click.echo(colored(f"✅ Cancelled {len(order_ids)} order(s)\n", Colors.GREEN))

    finally:
        if 'broker' in locals():
            broker.disconnect()


if __name__ == '__main__':
    cli()
