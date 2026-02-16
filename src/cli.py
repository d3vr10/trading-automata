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
from datetime import datetime
from decimal import Decimal
from typing import Optional

import click
import psycopg
from tabulate import tabulate

from config.settings import load_settings
from src.database.health import HealthCheckRegistry
from src.database.repository import TradeRepository


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


async def get_db_connection():
    """Get async database connection."""
    settings = load_settings()
    try:
        conn = await psycopg.AsyncConnection.connect(settings.database_url)
        return conn
    except Exception as e:
        click.echo(colored(f"❌ Failed to connect to database: {e}", Colors.RED))
        sys.exit(1)


@click.group()
def cli():
    """Trading Bot CLI - Check bot data and status."""
    pass


@cli.command()
@click.option('--format', type=click.Choice(['table', 'json']), default='table',
              help='Output format')
def status(format):
    """Check overall bot status."""
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


@cli.command()
@click.option('--limit', type=int, default=10, help='Number of trades to show')
@click.option('--symbol', type=str, default=None, help='Filter by symbol')
@click.option('--strategy', type=str, default=None, help='Filter by strategy')
def trades(limit, symbol, strategy):
    """View recent trades from database."""
    async def _trades():
        conn = await get_db_connection()
        repo = TradeRepository(conn)

        try:
            all_trades = await repo.get_trades_by_symbol(symbol) if symbol else []

            if not symbol:
                # Get all trades (fallback if method doesn't support all)
                result = await conn.execute(
                    f"""
                    SELECT id, symbol, strategy, broker, entry_price, entry_quantity,
                           exit_price, exit_quantity, pnl_percent, entry_timestamp, exit_timestamp
                    FROM trades
                    WHERE 1=1
                    {f"AND symbol = ${1}" if symbol else ""}
                    {f"AND strategy = ${1}" if strategy and not symbol else ""}
                    ORDER BY entry_timestamp DESC
                    LIMIT {limit}
                    """
                )
                trades_list = await result.fetchall()
            else:
                trades_list = all_trades[:limit]

            if not trades_list:
                click.echo(colored("No trades found", Colors.YELLOW))
                await conn.close()
                return

            click.echo(f"\n{colored('📊 Recent Trades', Colors.BOLD)}")
            click.echo(colored('=' * 120, Colors.CYAN))

            headers = ['ID', 'Symbol', 'Strategy', 'Side', 'Entry Price', 'Qty',
                      'Exit Price', 'Exit Qty', 'P&L %', 'Entry Time', 'Exit Time']

            rows = []
            for trade in trades_list:
                trade_id, sym, strat, broker, entry_price, entry_qty, exit_price, exit_qty, pnl, entry_ts, exit_ts = trade

                # Color code P&L
                pnl_str = f"{pnl:.2f}%" if pnl else "Open"
                if pnl and pnl > 0:
                    pnl_str = colored(pnl_str, Colors.GREEN)
                elif pnl and pnl < 0:
                    pnl_str = colored(pnl_str, Colors.RED)

                rows.append([
                    trade_id,
                    sym,
                    strat,
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
            await conn.close()

    asyncio.run(_trades())


@cli.command()
def metrics():
    """Show performance metrics."""
    async def _metrics():
        conn = await get_db_connection()
        repo = TradeRepository(conn)

        try:
            metrics_data = await repo.get_performance_metrics()

            if not metrics_data:
                click.echo(colored("No metrics available yet", Colors.YELLOW))
                await conn.close()
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
            await conn.close()

    asyncio.run(_metrics())


@cli.command()
def health():
    """Check bot health status."""
    async def _health():
        conn = await get_db_connection()
        registry = HealthCheckRegistry(conn)

        try:
            click.echo(f"\n{colored('🔋 Health Check Status', Colors.BOLD)}")
            click.echo(colored('=' * 80, Colors.CYAN))

            result = await conn.execute(
                """
                SELECT broker, strategy, is_healthy, connection_errors, last_bar_timestamp
                FROM health_checks
                ORDER BY last_check DESC
                """
            )
            checks = await result.fetchall()

            if not checks:
                click.echo(colored("No health checks recorded yet", Colors.YELLOW))
                await conn.close()
                return

            headers = ['Broker', 'Strategy', 'Status', 'Errors', 'Last Bar']
            rows = []

            for broker, strategy, is_healthy, errors, last_bar_ts in checks:
                status = colored('🟢 Healthy', Colors.GREEN) if is_healthy else colored('🔴 Unhealthy', Colors.RED)
                last_bar = last_bar_ts.strftime('%Y-%m-%d %H:%M:%S') if last_bar_ts else 'Never'
                rows.append([broker, strategy, status, errors, last_bar])

            click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
            click.echo()

        finally:
            await conn.close()

    asyncio.run(_health())


@cli.command()
def positions():
    """Show current open positions."""
    async def _positions():
        conn = await get_db_connection()

        try:
            result = await conn.execute(
                """
                SELECT symbol, strategy, entry_price, quantity, entry_timestamp
                FROM positions
                WHERE is_open = true
                ORDER BY entry_timestamp DESC
                """
            )
            positions_list = await result.fetchall()

            if not positions_list:
                click.echo(colored("No open positions", Colors.YELLOW))
                await conn.close()
                return

            click.echo(f"\n{colored('💼 Open Positions', Colors.BOLD)}")
            click.echo(colored('=' * 80, Colors.CYAN))

            headers = ['Symbol', 'Strategy', 'Entry Price', 'Quantity', 'Entry Time']
            rows = []

            for symbol, strategy, entry_price, quantity, entry_ts in positions_list:
                rows.append([
                    symbol,
                    strategy,
                    f"${float(entry_price):.2f}",
                    f"{float(quantity):.4f}",
                    entry_ts.strftime('%Y-%m-%d %H:%M:%S'),
                ])

            click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
            click.echo(f"\nTotal open positions: {len(positions_list)}")
            click.echo()

        finally:
            await conn.close()

    asyncio.run(_positions())


@cli.command()
def query():
    """Run custom SQL query on trading database."""
    click.echo(colored("Custom SQL Query Mode", Colors.BOLD))
    click.echo("Type 'exit' to quit\n")

    async def _query_loop():
        conn = await get_db_connection()

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

                    result = await conn.execute(sql)
                    rows = await result.fetchall()

                    if rows:
                        headers = [desc[0] for desc in result.description]
                        click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
                    else:
                        click.echo(colored("No results", Colors.YELLOW))

                except Exception as e:
                    click.echo(colored(f"Error: {e}", Colors.RED))

        finally:
            await conn.close()

    asyncio.run(_query_loop())


@cli.command()
@click.option('--table', type=click.Choice(['trades', 'positions', 'health_checks', 'performance_metrics']),
              required=True, help='Table to check schema for')
def schema(table):
    """Show database table schema."""
    async def _schema():
        conn = await get_db_connection()

        try:
            result = await conn.execute(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = $1
                ORDER BY ordinal_position
                """,
                table
            )
            columns = await result.fetchall()

            if not columns:
                click.echo(colored(f"Table '{table}' not found", Colors.RED))
                await conn.close()
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
            await conn.close()

    asyncio.run(_schema())


@cli.command()
def summary():
    """Show quick summary of everything."""
    async def _summary():
        conn = await get_db_connection()
        repo = TradeRepository(conn)

        try:
            # Count trades
            trades_result = await conn.execute("SELECT COUNT(*) FROM trades")
            trade_count = (await trades_result.fetchone())[0]

            # Get win rate
            metrics = await repo.get_performance_metrics()

            # Count open positions
            pos_result = await conn.execute("SELECT COUNT(*) FROM positions WHERE is_open = true")
            open_positions = (await pos_result.fetchone())[0]

            # Get health status
            health_result = await conn.execute("SELECT COUNT(*) FROM health_checks WHERE is_healthy = true")
            healthy_checks = (await health_result.fetchone())[0]

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
            await conn.close()

    asyncio.run(_summary())


@cli.command()
@click.option('--limit', default=50, help='Number of events to show')
@click.option('--symbol', default=None, help='Filter by symbol')
@click.option('--type', 'event_type', default=None, help='Filter by event type')
@click.option('--severity', default=None, help='Filter by severity level')
@click.option('--tail', is_flag=True, help='Show latest events (like tail -f)')
def events(limit, symbol, event_type, severity, tail):
    """View trading events and decisions.

    Shows strategy decisions, filter checks, signal generation, and order events.
    Use this to troubleshoot why the bot isn't making trades.
    """
    async def _events():
        conn = await get_db_connection()
        if conn is None:
            return

        try:
            # Build query
            query = "SELECT event_type, event_timestamp, severity, symbol, strategy, message, details FROM trading_events WHERE 1=1"
            params = []

            if symbol:
                query += " AND symbol = %s"
                params.append(symbol)

            if event_type:
                query += " AND event_type = %s"
                params.append(event_type)

            if severity:
                query += " AND severity = %s"
                params.append(severity)

            query += " ORDER BY event_timestamp DESC LIMIT %s"
            params.append(limit)

            result = await conn.execute(query, params)
            events_data = await result.fetchall()

            if not events_data:
                click.echo(colored("No events found", Colors.YELLOW))
                return

            click.echo(f"\n{colored('📊 Trading Events', Colors.BOLD)}")
            click.echo(colored('=' * 100, Colors.CYAN))

            # Format events for display
            rows = []
            for event in events_data:
                event_type_str, timestamp, sev, sym, strategy, msg, details = event

                # Color code by severity
                if sev == 'ERROR':
                    sev_colored = colored(sev, Colors.RED)
                elif sev == 'WARNING':
                    sev_colored = colored(sev, Colors.YELLOW)
                else:
                    sev_colored = colored(sev, Colors.GREEN)

                # Format timestamp
                ts_str = timestamp.strftime('%H:%M:%S') if hasattr(timestamp, 'strftime') else str(timestamp)

                rows.append([
                    ts_str,
                    colored(sym or '-', Colors.BLUE),
                    sev_colored,
                    event_type_str[:20],
                    msg[:50] + ('...' if len(msg) > 50 else ''),
                ])

            click.echo(tabulate(rows, headers=['Time', 'Symbol', 'Level', 'Type', 'Message'], tablefmt='simple'))
            click.echo()

        finally:
            await conn.close()

    asyncio.run(_events())


if __name__ == '__main__':
    cli()
