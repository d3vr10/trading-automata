"""Trade repository using SQLAlchemy ORM for database operations.

Uses async SQLAlchemy 2.0 with psycopg3 driver.
"""

import logging
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trading_automata.database.models import Trade, Position, HealthCheck

logger = logging.getLogger(__name__)


class TradeRepository:
    """Handles all trade database operations with SQLAlchemy ORM."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        """Initialize repository with async session factory.

        Args:
            session_factory: Async sessionmaker factory
        """
        self.session = session_factory

    async def record_trade_entry(
        self,
        symbol: str,
        strategy: str,
        broker: str,
        entry_price: Decimal,
        entry_quantity: Decimal,
        entry_order_id: Optional[str] = None,
        notes: Optional[str] = None,
        bot_name: Optional[str] = None,
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
            bot_name: Optional bot instance name (for multi-bot tracking)

        Returns:
            Trade ID for later reference
        """
        try:
            async with self.session() as session:
                trade = Trade(
                    symbol=symbol,
                    strategy=strategy,
                    broker=broker,
                    bot_name=bot_name,
                    entry_timestamp=datetime.now(UTC),
                    entry_price=entry_price,
                    entry_quantity=entry_quantity,
                    entry_order_id=entry_order_id,
                    notes=notes,
                )
                session.add(trade)
                await session.commit()
                await session.refresh(trade)
                log_msg = f"Trade entry recorded: {symbol} {entry_quantity} @ {entry_price} (ID: {trade.id})"
                if bot_name:
                    log_msg = f"[{bot_name}] {log_msg}"
                logger.info(log_msg)
                return trade.id
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
        try:
            async with self.session() as session:
                trade = await session.get(Trade, trade_id)
                if not trade:
                    logger.error(f"Trade not found: ID {trade_id}")
                    return

                # Calculate P&L in Python (not SQL)
                entry_price = Decimal(str(trade.entry_price))
                gross_pnl = (exit_price - entry_price) * exit_quantity
                pnl_percent = ((exit_price - entry_price) / entry_price) * 100 if entry_price != 0 else Decimal(0)

                # Update trade with exit details
                trade.exit_timestamp = datetime.now(UTC)
                trade.exit_price = exit_price
                trade.exit_quantity = exit_quantity
                trade.exit_order_id = exit_order_id
                trade.gross_pnl = gross_pnl
                trade.pnl_percent = float(pnl_percent)
                trade.is_winning_trade = gross_pnl > 0

                # Calculate hold duration
                if trade.entry_timestamp:
                    hold_duration = datetime.now(UTC) - trade.entry_timestamp
                    trade.hold_duration_seconds = int(hold_duration.total_seconds())

                await session.commit()
                logger.info(f"Trade exit recorded: ID {trade_id} @ {exit_price}")
        except Exception as e:
            logger.error(f"Failed to record trade exit: {e}")
            raise

    async def get_trades_by_symbol(
        self,
        symbol: str,
        days: int = 7,
        limit: int = 100,
        bot_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent trades for a symbol.

        Args:
            symbol: Trading symbol
            days: Look back N days
            limit: Maximum trades to return
            bot_name: Optional bot instance name (filters by bot if provided)

        Returns:
            List of trade records as dictionaries
        """
        try:
            async with self.session() as session:
                cutoff_date = datetime.now(UTC) - timedelta(days=days)
                conditions = [
                    Trade.symbol == symbol,
                    Trade.entry_timestamp > cutoff_date,
                ]
                if bot_name:
                    conditions.append(Trade.bot_name == bot_name)

                stmt = (
                    select(Trade)
                    .where(and_(*conditions))
                    .order_by(Trade.entry_timestamp.desc())
                    .limit(limit)
                )
                result = await session.execute(stmt)
                trades = result.scalars().all()

                # Convert to dictionaries for compatibility
                return [
                    {
                        'id': t.id,
                        'symbol': t.symbol,
                        'strategy': t.strategy,
                        'broker': t.broker,
                        'entry_timestamp': t.entry_timestamp,
                        'entry_price': t.entry_price,
                        'entry_quantity': t.entry_quantity,
                        'entry_order_id': t.entry_order_id,
                        'exit_timestamp': t.exit_timestamp,
                        'exit_price': t.exit_price,
                        'exit_quantity': t.exit_quantity,
                        'exit_order_id': t.exit_order_id,
                        'gross_pnl': t.gross_pnl,
                        'pnl_percent': t.pnl_percent,
                        'is_winning_trade': t.is_winning_trade,
                        'hold_duration_seconds': t.hold_duration_seconds,
                    }
                    for t in trades
                ]
        except Exception as e:
            logger.error(f"Failed to get trades for {symbol}: {e}")
            return []

    async def get_trades_by_strategy(
        self,
        strategy: str,
        days: int = 7,
        limit: int = 100,
        bot_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get trades by strategy.

        Args:
            strategy: Strategy name
            days: Look back N days
            limit: Maximum trades to return
            bot_name: Optional bot instance name (filters by bot if provided)

        Returns:
            List of trade records as dictionaries
        """
        try:
            async with self.session() as session:
                cutoff_date = datetime.now(UTC) - timedelta(days=days)
                conditions = [
                    Trade.strategy == strategy,
                    Trade.entry_timestamp > cutoff_date,
                ]
                if bot_name:
                    conditions.append(Trade.bot_name == bot_name)

                stmt = (
                    select(Trade)
                    .where(and_(*conditions))
                    .order_by(Trade.entry_timestamp.desc())
                    .limit(limit)
                )
                result = await session.execute(stmt)
                trades = result.scalars().all()

                # Convert to dictionaries for compatibility
                return [
                    {
                        'id': t.id,
                        'symbol': t.symbol,
                        'strategy': t.strategy,
                        'broker': t.broker,
                        'entry_timestamp': t.entry_timestamp,
                        'entry_price': t.entry_price,
                        'entry_quantity': t.entry_quantity,
                        'entry_order_id': t.entry_order_id,
                        'exit_timestamp': t.exit_timestamp,
                        'exit_price': t.exit_price,
                        'exit_quantity': t.exit_quantity,
                        'exit_order_id': t.exit_order_id,
                        'gross_pnl': t.gross_pnl,
                        'pnl_percent': t.pnl_percent,
                        'is_winning_trade': t.is_winning_trade,
                    }
                    for t in trades
                ]
        except Exception as e:
            logger.error(f"Failed to get trades for strategy {strategy}: {e}")
            return []

    async def get_performance_metrics(
        self,
        strategy: Optional[str] = None,
        days: int = 7,
        bot_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get performance metrics for a strategy.

        Args:
            strategy: Strategy name (None for all)
            days: Look back N days
            bot_name: Optional bot instance name (filters by bot if provided)

        Returns:
            Dictionary with metrics
        """
        try:
            async with self.session() as session:
                cutoff_date = datetime.now(UTC) - timedelta(days=days)

                # Build query
                conditions = [
                    Trade.entry_timestamp > cutoff_date,
                    Trade.exit_timestamp.isnot(None),
                ]
                if strategy:
                    conditions.append(Trade.strategy == strategy)
                if bot_name:
                    conditions.append(Trade.bot_name == bot_name)

                stmt = select(Trade).where(and_(*conditions))

                result = await session.execute(stmt)
                trades = result.scalars().all()

                if not trades:
                    return {
                        'total_trades': 0,
                        'winning_trades': 0,
                        'losing_trades': 0,
                        'win_rate': 0.0,
                        'gross_profit': Decimal(0),
                        'gross_loss': Decimal(0),
                        'net_profit': Decimal(0),
                        'profit_factor': 0.0,
                    }

                # Calculate metrics in Python
                total_trades = len(trades)
                winning_trades = sum(1 for t in trades if t.is_winning_trade)
                losing_trades = total_trades - winning_trades

                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

                gross_profit = sum(t.gross_pnl for t in trades if t.gross_pnl and t.gross_pnl > 0)
                gross_loss = sum(abs(t.gross_pnl) for t in trades if t.gross_pnl and t.gross_pnl < 0)
                net_profit = sum(t.gross_pnl for t in trades if t.gross_pnl)

                profit_factor = (float(gross_profit) / float(gross_loss)) if gross_loss > 0 else 0.0

                return {
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'losing_trades': losing_trades,
                    'win_rate': round(win_rate, 2),
                    'gross_profit': round(gross_profit, 2),
                    'gross_loss': round(gross_loss, 2),
                    'net_profit': round(net_profit, 2),
                    'profit_factor': round(profit_factor, 2),
                }
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return {}

    async def get_open_positions(
        self,
        strategy: Optional[str] = None,
        bot_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get currently open positions.

        Args:
            strategy: Filter by strategy (None for all)
            bot_name: Optional bot instance name (filters by bot if provided)

        Returns:
            List of open position records as dictionaries
        """
        try:
            async with self.session() as session:
                conditions = [Position.is_open == True]
                if strategy:
                    conditions.append(Position.strategy == strategy)
                if bot_name:
                    conditions.append(Position.bot_name == bot_name)

                stmt = select(Position).where(and_(*conditions))

                stmt = stmt.order_by(Position.opened_at.desc())

                result = await session.execute(stmt)
                positions = result.scalars().all()

                # Convert to dictionaries for compatibility
                return [
                    {
                        'id': p.id,
                        'symbol': p.symbol,
                        'strategy': p.strategy,
                        'broker': p.broker,
                        'quantity': p.quantity,
                        'entry_price': p.entry_price,
                        'current_price': p.current_price,
                        'stop_loss': p.stop_loss,
                        'take_profit': p.take_profit,
                        'opened_at': p.opened_at,
                    }
                    for p in positions
                ]
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
        bot_name: Optional[str] = None,
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
            bot_name: Optional bot instance name (for multi-bot tracking)

        Returns:
            Position ID
        """
        try:
            async with self.session() as session:
                position = Position(
                    symbol=symbol,
                    strategy=strategy,
                    broker=broker,
                    bot_name=bot_name,
                    quantity=quantity,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    is_open=True,
                )
                session.add(position)
                await session.commit()
                await session.refresh(position)
                log_msg = f"Position recorded: {symbol} {quantity} (ID: {position.id})"
                if bot_name:
                    log_msg = f"[{bot_name}] {log_msg}"
                logger.info(log_msg)
                return position.id
        except Exception as e:
            logger.error(f"Failed to record position: {e}")
            raise

    async def close_position(self, position_id: int, realized_pnl: Decimal) -> None:
        """Close an open position.

        Args:
            position_id: Position ID
            realized_pnl: Realized P&L
        """
        try:
            async with self.session() as session:
                position = await session.get(Position, position_id)
                if not position:
                    logger.error(f"Position not found: ID {position_id}")
                    return

                position.is_open = False
                position.realized_pnl = realized_pnl
                position.closed_at = datetime.now(UTC)

                await session.commit()
                logger.info(f"Position closed: ID {position_id}, P&L: {realized_pnl}")
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            raise
