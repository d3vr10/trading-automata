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


def build_bot_config_from_recovery(recovery_item: Dict[str, Any]) -> tuple[Dict[str, Any], int, str]:
    """Convert API recovery item to BotConfig format.

    Args:
        recovery_item: Item from GET /api/bots/recovery/pending

    Returns:
        Tuple of (bot_config_dict, user_id, desired_state)
        bot_config_dict is compatible with BotConfig Pydantic model
    """
    from decimal import Decimal

    config = {
        "name": recovery_item["bot_name"],
        "enabled": True,
        "broker": {
            "type": recovery_item["broker_type"],
            "environment": recovery_item["environment"],
            "api_key": recovery_item["api_key"],
            "secret_key": recovery_item["secret_key"],
            "passphrase": recovery_item.get("passphrase", ""),
        },
        "allocation": {
            "type": "dollars",
            "amount": Decimal(str(recovery_item["allocation"])),
        },
        "fence": {
            "type": recovery_item["fence_type"],
            "overage_pct": recovery_item["fence_overage_pct"],
        },
        "risk": {
            "stop_loss_pct": recovery_item["stop_loss_pct"],
            "take_profit_pct": recovery_item["take_profit_pct"],
            "max_position_size": recovery_item["max_position_size"],
            "trailing_stop": recovery_item.get("trailing_stop", False),
            "trailing_stop_pct": recovery_item.get("trailing_stop_pct", 1.5),
            "trailing_activation_pct": recovery_item.get("trailing_activation_pct", 1.0),
            "take_profit_targets": recovery_item.get("take_profit_targets") or [],
        },
        "trade_frequency": {
            "poll_interval_minutes": recovery_item["poll_interval_minutes"],
        },
        "strategy_config": "config/strategies.yaml",
    }

    return config, recovery_item["user_id"], recovery_item["desired_state"]


async def fetch_fresh_credentials(
    api_url: str, bot_name: str, user_id: int,
) -> Optional[Dict[str, str]]:
    """Fetch current decrypted credentials for a running bot.

    Called when the engine detects an auth failure (401/403) on a broker
    connection, indicating credentials may have been rotated via the dashboard.

    Args:
        api_url: Base URL of the API service
        bot_name: Bot name to look up
        user_id: Owner user ID

    Returns:
        Dict with api_key, secret_key, passphrase — or None on failure.
    """
    endpoint = f"{api_url}/api/bots/credentials/refresh/{bot_name}?user_id={user_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Fetched fresh credentials for bot '{bot_name}'")
                    return data
                else:
                    logger.warning(f"Credential refresh returned {resp.status} for '{bot_name}'")
                    return None
    except Exception as e:
        logger.warning(f"Failed to fetch credentials for '{bot_name}': {e}")
        return None
