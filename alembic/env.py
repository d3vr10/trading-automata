"""Alembic environment for database migrations.

Uses SQLAlchemy with psycopg3 for PostgreSQL connections (synchronous mode).
Run migrations with: alembic upgrade head
"""

import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set sqlalchemy.url from environment variable
database_url = os.getenv(
    'DATABASE_URL',
    'postgresql://postgres:postgres@localhost:5432/trading_bot'
)
config.set_main_option("sqlalchemy.url", database_url)

# For generic (non-ORM) migrations using raw SQL
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with SQLAlchemy.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Get database URL from config
    db_url = config.get_main_option("sqlalchemy.url")

    # Handle postgres:// scheme (convert to postgresql+psycopg for psycopg3)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif db_url.startswith("postgresql://"):
        # Explicitly use psycopg3 driver
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

    # Create SQLAlchemy engine with psycopg3
    engine = create_engine(db_url, poolclass=pool.StaticPool)

    with engine.connect() as connection:
        # Define process_revision_directives
        def process_revision_directives(context, revision, directives):
            if getattr(config.cmd_opts, 'autogenerate', False):
                script = directives[0]
                if script.upgrade_ops.is_empty():
                    directives[:] = []

        # Configure the Alembic context with the connection
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
            compare_type=True,
            compare_server_default=True,
        )

        # Run migrations within a transaction
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
