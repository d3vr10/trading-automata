"""Trading bot entry point.

Uses BotOrchestrator to handle all bot configurations:
- Single bot: Define one bot in config/bots.yaml
- Multiple bots: Define multiple bots in config/bots.yaml
- Per-bot configs: Optionally place individual configs in config/bots/*.yaml

All bot configurations are loaded from config/bots.yaml and merged
with environment variables (which take precedence).
"""

import asyncio
import logging
import os
import sys

import sentry_sdk

from trading_automata.monitoring.logger import setup_logging, get_logger

# Initialize logging before anything else
_log_level = os.environ.get("LOG_LEVEL", "INFO")
setup_logging(level=_log_level, log_file="logs/trading-automata.log")

logger = get_logger(__name__)

# Initialize Sentry (no-op if DSN is empty)
_sentry_dsn = os.environ.get("SENTRY_DSN", "")
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=os.environ.get("ENVIRONMENT", "development"),
        traces_sample_rate=0.1,
        send_default_pii=False,
    )


def main():
    """Main entry point - uses multi-bot orchestrator.

    The BotOrchestrator handles all bot configurations:
    - Single bot: Create config/bots.yaml with one bot entry
    - Multiple bots: Add multiple bot entries to config/bots.yaml
    - Per-bot configs: Place individual bot configs in config/bots/*.yaml (optional)
    """
    logger.info("=" * 60)
    logger.info("🤖 Trading Bot Startup")
    logger.info("=" * 60)

    try:
        # Always use the orchestrator - it handles single and multiple bots
        logger.info("🔄 Loading bot configuration from config/bots.yaml...")
        from trading_automata.orchestration.orchestrator import BotOrchestrator
        orchestrator = BotOrchestrator()
        asyncio.run(orchestrator.start())
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
