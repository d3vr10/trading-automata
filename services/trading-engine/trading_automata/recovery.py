"""Bot recovery on engine startup — restore bots from API desired_state."""

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from trading_automata.monitoring.logger import get_logger

logger = get_logger(__name__)


async def fetch_recovery_bots(api_url: str) -> List[Dict[str, Any]]:
    """Fetch all bots that should be recovered from the API service.

    Calls GET /api/bots/recovery/pending to get all bots with
    desired_state IN ('running', 'paused') across all users.

    Args:
        api_url: Base URL of the API service (e.g., http://api:8000)

    Returns:
        List of bot recovery items with user_id, bot_id, bot_name, and config.
        Returns empty list on error.
    """
    endpoint = f"{api_url}/api/bots/recovery/pending"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    items = await resp.json()
                    logger.info(f"Fetched {len(items)} bot(s) for recovery")
                    return items
                else:
                    logger.warning(f"Recovery endpoint returned {resp.status}: {await resp.text()}")
                    return []
    except Exception as e:
        logger.warning(f"Failed to fetch recovery bots from {endpoint}: {e}")
        return []


def build_bot_config_from_recovery(recovery_item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert API recovery item to BotConfig format.

    Args:
        recovery_item: Item from GET /api/bots/recovery/pending

    Returns:
        Bot configuration dict compatible with BotInstance
    """
    return {
        "name": recovery_item["bot_name"],
        "strategy_id": recovery_item["strategy_id"],
        "enabled": True,
        "broker": {
            "type": recovery_item["broker_type"],
            "environment": recovery_item["environment"],
            "api_key": recovery_item["api_key"],
            "secret_key": recovery_item["secret_key"],
            "passphrase": recovery_item.get("passphrase", ""),
        },
        "risk_management": {
            "allocation": recovery_item["allocation"],
            "fence_type": recovery_item["fence_type"],
            "fence_overage_pct": recovery_item["fence_overage_pct"],
        },
        "trading": {
            "stop_loss_pct": recovery_item["stop_loss_pct"],
            "take_profit_pct": recovery_item["take_profit_pct"],
            "max_position_size": recovery_item["max_position_size"],
        },
        "polling": {
            "poll_interval_minutes": recovery_item["poll_interval_minutes"],
        },
        "user_id": recovery_item["user_id"],
        "desired_state": recovery_item["desired_state"],
    }
