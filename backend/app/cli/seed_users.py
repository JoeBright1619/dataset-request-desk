"""CLI command to seed initial users.

Usage:
    python -m app.cli.seed_users

This is idempotent - running it multiple times is safe.
"""

import asyncio
import logging
import sys

from app.db.session import SessionFactory
from app.services.seed_service import seed_users

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> int:
    """Run the seed users command."""
    logger.info("Starting user seed process...")

    try:
        async with SessionFactory() as session:
            result = await seed_users(session)

        logger.info(
            f"Seed complete: {result['created']} created, {result['existing']} existing"
        )
        return 0

    except Exception as e:
        logger.error(f"Seed failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
