"""Database initialization using Alembic migrations.

This script applies all pending migrations to initialize/update the database.
Usage: python -m src.database.init

Alembic handles versioning and tracks applied migrations.
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from alembic.config import Config
from alembic.command import upgrade

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database(database_url: str) -> None:
    """Initialize PostgreSQL database with Alembic migrations.

    Args:
        database_url: PostgreSQL connection string
            e.g., postgresql://user:password@localhost:5432/trading_bot
    """
    try:
        # Get path to alembic.ini
        alembic_ini = Path(__file__).parent.parent.parent / "alembic" / "alembic.ini"

        if not alembic_ini.exists():
            raise FileNotFoundError(f"Alembic config not found: {alembic_ini}")

        # Configure Alembic
        config = Config(str(alembic_ini))
        config.set_main_option("sqlalchemy.url", database_url)

        logger.info(f"✅ Connecting to database: {database_url}")

        # Run migrations
        logger.info("Running database migrations...")
        upgrade(config, "head")

        logger.info("✅ Database initialization complete!")
        logger.info("✅ All migrations applied successfully")

    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise


def main():
    """Main entry point."""
    try:
        from config.settings import load_settings

        settings = load_settings()
        database_url = settings.database_url

        logger.info(f"Initializing database: {database_url}")
        init_database(database_url)

    except Exception as e:
        logger.error(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
