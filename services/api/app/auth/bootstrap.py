"""Root user bootstrap — creates the initial root account on first startup.

Follows the Elasticsearch pattern: on first boot, if no users exist,
create a root user and display credentials prominently.

Priority for credentials (highest to lowest):
  1. CLI arguments (not applicable at API service startup)
  2. Environment variables: ROOT_USERNAME, ROOT_PASSWORD
  3. config.yml auth section (future)
  4. Auto-generated random 32-char token
"""

import logging
import secrets
import string

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.password import hash_password
from app.config import settings
from app.models import User

logger = logging.getLogger(__name__)

BANNER_WIDTH = 61


def _generate_random_password(length: int = 32) -> str:
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _print_credentials_banner(username: str, password: str) -> None:
    """Print credentials in a prominent Elasticsearch-style banner."""
    separator = "\u2501" * BANNER_WIDTH
    print(f"\n{separator}")
    print("\U0001f510  Trading Automata Security Configuration")
    print(separator)
    print()
    print("The root user has been created with the following credentials:")
    print()
    print(f"  Username: {username}")
    print(f"  Password: {password}")
    print()
    print("Please store these credentials securely.")
    print("You can change the password via the dashboard or CLI.")
    print()
    print(f"{separator}\n")


async def bootstrap_root_user(session: AsyncSession) -> None:
    """Create the root user if no users exist in the database.

    This should be called during application startup (FastAPI lifespan).
    """
    # Check if any users exist
    result = await session.execute(select(func.count()).select_from(User))
    user_count = result.scalar()

    if user_count > 0:
        logger.debug(f"Database has {user_count} user(s), skipping root bootstrap")
        return

    # Determine credentials
    username = settings.root_username
    password = settings.root_password

    generated = False
    if not password:
        password = _generate_random_password()
        generated = True

    # Create root user
    root_user = User(
        username=username,
        password_hash=hash_password(password),
        role="root",
        is_active=True,
    )
    session.add(root_user)
    await session.commit()

    # Display credentials
    _print_credentials_banner(username, password)

    if generated:
        logger.warning(
            "Root password was auto-generated. "
            "Set ROOT_PASSWORD environment variable to use a specific password."
        )

    logger.info(f"Root user '{username}' created successfully")
