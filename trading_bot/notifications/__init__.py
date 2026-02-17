"""Notifications module for trading bot.

Handles alerts and notifications via Telegram and other channels.
"""

from trading_bot.notifications.telegram_bot import TradingBotTelegram

__all__ = ["TradingBotTelegram"]
