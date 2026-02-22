"""Config loader for multi-bot orchestration system.

Supports two configuration modes:
1. Centralized: single config/bots.yaml with global and bots list
2. Distributed: config/bots/ directory with per-bot YAML files + optional global section in bots.yaml

Precedence (highest to lowest):
- Environment variables (e.g., ALPACA_API_KEY)
- Per-bot/global YAML values
- Pydantic field defaults
"""

import os
import logging
from pathlib import Path
from typing import Optional

import yaml

from trading_bot.config.bot_config import OrchestratorConfig, GlobalConfig, BotConfig


logger = logging.getLogger(__name__)


def _expand_env_vars(value):
    """Expand environment variables in string values.

    Examples:
        "${ALPACA_API_KEY}" -> os.environ.get('ALPACA_API_KEY')
        "postgresql://user:${DB_PASS}@localhost/db" -> expands ${DB_PASS}
    """
    if not isinstance(value, str):
        return value

    import re

    def replace_var(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    return re.sub(r'\$\{([^}]+)\}', replace_var, value)


def _recursively_expand_env_vars(obj):
    """Recursively expand environment variables in a dict or list."""
    if isinstance(obj, dict):
        return {k: _recursively_expand_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_recursively_expand_env_vars(item) for item in obj]
    elif isinstance(obj, str):
        return _expand_env_vars(obj)
    else:
        return obj


def load_bot_configs(
    config_dir: str = "config",
    bots_yaml: str = "config/bots.yaml",
    bots_dir: str = "config/bots",
) -> OrchestratorConfig:
    """Load bot configurations from YAML files.

    Supports two modes:
    1. Centralized: config/bots.yaml with `global:` and `bots:` sections
    2. Distributed: config/bots/*.yaml files (each is one BotConfig) + optional `global:` in bots.yaml

    Args:
        config_dir: Base config directory
        bots_yaml: Path to main bots.yaml file
        bots_dir: Path to bots/ directory for per-bot configs

    Returns:
        OrchestratorConfig with validated settings

    Raises:
        FileNotFoundError: If no config files found
        yaml.YAMLError: If YAML is invalid
        ValueError: If config validation fails
    """
    bots_yaml_path = Path(bots_yaml)
    bots_dir_path = Path(bots_dir)

    # Check if either config source exists
    has_bots_yaml = bots_yaml_path.exists()
    has_bots_dir = bots_dir_path.exists() and bots_dir_path.is_dir()

    if not has_bots_yaml and not has_bots_dir:
        raise FileNotFoundError(
            f"No bot configuration found. "
            f"Create either {bots_yaml} or directory {bots_dir}/"
        )

    # Load global config
    global_data = {}
    if has_bots_yaml:
        with open(bots_yaml_path) as f:
            root = yaml.safe_load(f) or {}
            if 'global' in root:
                global_data = root.get('global', {})

    # Expand env vars in global config
    global_data = _recursively_expand_env_vars(global_data)

    # Create GlobalConfig with precedence: env vars > YAML > defaults
    global_config_dict = global_data.copy()

    # Apply environment variable overrides for common settings
    env_overrides = {
        'database_url': 'DATABASE_URL',
        'telegram_token': 'TELEGRAM_TOKEN',
        'telegram_chat_id': 'TELEGRAM_CHAT_ID',
        'log_level': 'LOG_LEVEL',
        'log_file': 'LOG_FILE',
    }
    for config_key, env_var in env_overrides.items():
        if env_var in os.environ:
            global_config_dict[config_key] = os.environ[env_var]

    global_config = GlobalConfig(**global_config_dict)

    # Load bot configs
    bots = []

    # Mode 1: Centralized bots.yaml
    if has_bots_yaml:
        with open(bots_yaml_path) as f:
            root = yaml.safe_load(f) or {}
            if 'bots' in root:
                bots_data = root['bots']
                for bot_data in bots_data:
                    bot_data = _recursively_expand_env_vars(bot_data)
                    bots.append(BotConfig(**bot_data))

    # Mode 2: Distributed bots/ directory (PLUS anything from centralized)
    if has_bots_dir:
        yaml_files = sorted(bots_dir_path.glob('*.yaml'))
        for yaml_file in yaml_files:
            with open(yaml_file) as f:
                bot_data = yaml.safe_load(f) or {}
                bot_data = _recursively_expand_env_vars(bot_data)
                # Ensure 'name' is set (either from file or filename)
                if 'name' not in bot_data:
                    bot_data['name'] = yaml_file.stem
                bots.append(BotConfig(**bot_data))

    # Deduplicate by bot name (distributed files override centralized if same name)
    seen_names = set()
    unique_bots = []
    for bot in reversed(bots):  # Process in reverse so earlier entries override
        if bot.name not in seen_names:
            unique_bots.append(bot)
            seen_names.add(bot.name)
    bots = list(reversed(unique_bots))  # Restore original order

    if not bots:
        raise ValueError(
            f"No bot configurations found in {bots_yaml} or {bots_dir}/. "
            f"Create at least one bot configuration."
        )

    logger.info(f"Loaded {len(bots)} bot configuration(s): {[b.name for b in bots]}")

    return OrchestratorConfig(global_config=global_config, bots=bots)
