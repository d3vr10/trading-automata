"""Trade repository using raw psycopg3 for database operations.

Simple, fast, and API-ready. No ORM overhead.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

import psycopg
from psycopg import AsyncConnection

logger = logging.getLogger(__name__)


class TradeRepository:
    """Handles all trade database operations with raw SQL."""

    def __init__(self, connection: AsyncConnection):
        """Initialize repository with database connection.

        Args:
            connection: Async psycopg connection
        """
        self.conn = connection

    async def record_trade_entry(
        self,
        symbol: str,
        strategy: str,
        broker: str,
        entry_price: Decimal,
        entry_quantity: Decimal,
        entry_order_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        """Record a trade entry (opening position).

        Args:
            symbol: Trading symbol (e.g., 'BTC/USD')
            strategy: Strategy name
            broker: Broker name
            entry_price: Entry price
            entry_quantity: Quantity entered
            entry_order_id: Optional order ID from broker
            notes: Optional notes about the trade

        Returns:
            Trade ID for later reference
        """
        query = """
            INSERT INTO trades (
                symbol, strategy, broker, entry_timestamp,
                entry_price, entry_quantity, entry_order_id, notes
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """

        try:
            result = await self.conn.execute(
                query,
                symbol,
                strategy,
                broker,
                datetime.utcnow(),
                float(entry_price),
                float(entry_quantity),
                entry_order_id,
                notes,
            )
            trade_id = result[0]
            logger.info(f"Trade entry recorded: {symbol} {entry_quantity} @ {entry_price} (ID: {trade_id})")
            return trade_id
        except Exception as e:
            logger.error(f"Failed to record trade entry: {e}")
            raise

    async def record_trade_exit(
        self,
        trade_id: int,
        exit_price: Decimal,
        exit_quantity: Decimal,
        exit_order_id: Optional[str] = None,
    ) -> None:
        """Record a trade exit (closing position).

        Args:
            trade_id: ID from record_trade_entry
            exit_price: Exit price
            exit_quantity: Quantity exited
            exit_order_id: Optional order ID from broker
        """
        query = """
            UPDATE trades
            SET
                exit_timestamp = $1,
                exit_price = $2,
                exit_quantity = $3,
                exit_order_id = $4,
                gross_pnl = ($5 - $6) * $3,
                pnl_percent = (($5 - $6) / $6) * 100,
                is_winning_trade = ($5 > $6),
                hold_duration_seconds = EXTRACT(EPOCH FROM ($1 - entry_timestamp))::INTEGER
            WHERE id = $7
        """

        try:
            await self.conn.execute(
                query,
                datetime.utcnow(),
                float(exit_price),
                float(exit_quantity),
                exit_order_id,
                float(exit_price),
                float(exit_price),  # Will be replaced with actual entry price
                trade_id,
            )
            logger.info(f"Trade exit recorded: ID {trade_id} @ {exit_price}")
        except Exception as e:
            logger.error(f"Failed to record trade exit: {e}")
            raise

    async def get_trades_by_symbol(
        self,
        symbol: str,
        days: int = 7,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get recent trades for a symbol.

        Args:
            symbol: Trading symbol
            days: Look back N days
            limit: Maximum trades to return

        Returns:
            List of trade records
        """
        query = """
            SELECT
                id, symbol, strategy, broker,
                entry_timestamp, entry_price, entry_quantity,
                exit_timestamp, exit_price, exit_quantity,
                gross_pnl, pnl_percent, is_winning_trade,
                hold_duration_seconds
            FROM trades
            WHERE symbol = $1
              AND entry_timestamp > NOW() - INTERVAL '1 day' * $2
            ORDER BY entry_timestamp DESC
            LIMIT $3
        """

        try:
            rows = await self.conn.execute(query, symbol, days, limit)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get trades for {symbol}: {e}")
            return []

    async def get_trades_by_strategy(
        self,
        strategy: str,
        days: int = 7,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get trades by strategy.

        Args:
            strategy: Strategy name
            days: Look back N days
            limit: Maximum trades to return

        Returns:
            List of trade records
        """
        query = """
            SELECT
                id, symbol, strategy, broker,
                entry_timestamp, entry_price, entry_quantity,
                exit_timestamp, exit_price, exit_quantity,
                gross_pnl, pnl_percent, is_winning_trade
            FROM trades
            WHERE strategy = $1
              AND entry_timestamp > NOW() - INTERVAL '1 day' * $2
            ORDER BY entry_timestamp DESC
            LIMIT $3
        """

        try:
            rows = await self.conn.execute(query, strategy, days, limit)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get trades for strategy {strategy}: {e}")
            return []

    async def get_performance_metrics(
        self,
        strategy: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get performance metrics for a strategy.

        Args:
            strategy: Strategy name (None for all)
            days: Look back N days

        Returns:
            Dictionary with metrics
        """
        where_clause = ""
        params = [days]

        if strategy:
            where_clause = "WHERE strategy = $2"
            params = [days, strategy]

        query = f"""
            SELECT
                COUNT(*) as total_trades,
                COUNT(CASE WHEN is_winning_trade = true THEN 1 END) as winning_trades,
                COUNT(CASE WHEN is_winning_trade = false THEN 1 END) as losing_trades,
                ROUND(
                    COUNT(CASE WHEN is_winning_trade = true THEN 1 END)::NUMERIC
                    / NULLIF(COUNT(*), 0) * 100, 2
                ) as win_rate,
                ROUND(SUM(CASE WHEN gross_pnl > 0 THEN gross_pnl ELSE 0 END)::NUMERIC, 2) as gross_profit,
                ROUND(SUM(CASE WHEN gross_pnl < 0 THEN ABS(gross_pnl) ELSE 0 END)::NUMERIC, 2) as gross_loss,
                ROUND(SUM(gross_pnl)::NUMERIC, 2) as net_profit,
                ROUND(
                    SUM(CASE WHEN gross_pnl > 0 THEN gross_pnl ELSE 0 END)::NUMERIC /
                    NULLIF(SUM(CASE WHEN gross_pnl < 0 THEN ABS(gross_pnl) ELSE 0 END), 0), 2
                ) as profit_factor
            FROM trades
            {where_clause}
              AND entry_timestamp > NOW() - INTERVAL '1 day' * $1
              AND exit_timestamp IS NOT NULL
        """

        try:
            result = await self.conn.execute(query, *params)
            row = result[0] if result else None

            if not row:
                return {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate': 0,
                    'gross_profit': 0,
                    'gross_loss': 0,
                    'net_profit': 0,
                    'profit_factor': 0,
                }

            return dict(row)
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return {}

    async def get_open_positions(self, strategy: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get currently open positions.

        Args:
            strategy: Filter by strategy (None for all)

        Returns:
            List of open position records
        """
        where_clause = "WHERE is_open = true"
        params = []

        if strategy:
            where_clause += " AND strategy = $1"
            params = [strategy]

        query = f"""
            SELECT
                id, symbol, strategy, broker,
                quantity, entry_price, current_price,
                stop_loss, take_profit,
                opened_at
            FROM positions
            {where_clause}
            ORDER BY opened_at DESC
        """

        try:
            rows = await self.conn.execute(query, *params)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get open positions: {e}")
            return []

    async def record_position(
        self,
        symbol: str,
        strategy: str,
        broker: str,
        quantity: Decimal,
        entry_price: Decimal,
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
    ) -> int:
        """Record an open position.

        Args:
            symbol: Trading symbol
            strategy: Strategy name
            broker: Broker name
            quantity: Position size
            entry_price: Entry price
            stop_loss: Optional stop loss price
            take_profit: Optional take profit price

        Returns:
            Position ID
        """
        query = """
            INSERT INTO positions (
                symbol, strategy, broker, quantity, entry_price,
                stop_loss, take_profit, is_open
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, true)
            RETURNING id
        """

        try:
            result = await self.conn.execute(
                query,
                symbol,
                strategy,
                broker,
                float(quantity),
                float(entry_price),
                float(stop_loss) if stop_loss else None,
                float(take_profit) if take_profit else None,
            )
            position_id = result[0]
            logger.info(f"Position recorded: {symbol} {quantity} (ID: {position_id})")
            return position_id
        except Exception as e:
            logger.error(f"Failed to record position: {e}")
            raise

    async def close_position(self, position_id: int, realized_pnl: Decimal) -> None:
        """Close an open position.

        Args:
            position_id: Position ID
            realized_pnl: Realized P&L
        """
        query = """
            UPDATE positions
            SET
                is_open = false,
                realized_pnl = $1,
                closed_at = NOW()
            WHERE id = $2
        """

        try:
            await self.conn.execute(query, float(realized_pnl), position_id)
            logger.info(f"Position closed: ID {position_id}, P&L: {realized_pnl}")
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            raise
