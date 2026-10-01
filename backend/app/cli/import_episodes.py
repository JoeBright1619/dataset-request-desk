"""CLI command to import episodes from a CSV file.

Usage:
    python -m app.cli.import_episodes <file_path>
    python -m app.cli import-episodes <file_path>

This is idempotent - running it multiple times ignores existing episode_ids.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

from app.db.session import SessionFactory
from app.services.episode_import_service import EpisodeImportService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main(args: list[str] | None = None) -> int:
    """Run the import episodes command."""
    if args is None:
        args = sys.argv[1:]

    if not args:
        print("Usage: python -m app.cli import-episodes <file_path>")
        return 1

    file_path = Path(args[0])
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return 1

    if not file_path.is_file():
        logger.error(f"Not a regular file: {file_path}")
        return 1

    logger.info(f"Starting episode import from {file_path}...")

    try:
        with file_path.open("r", encoding="utf-8") as f:
            async with SessionFactory() as session:
                summary = await EpisodeImportService(session).import_csv(f)

        print(json.dumps(summary.as_dict(), indent=2))
        logger.info(
            "Import complete: %s imported, %s skipped duplicates, %s invalid",
            summary.imported,
            summary.skipped_duplicates,
            summary.invalid,
        )
        return 0

    except Exception as e:
        logger.error(f"Episode import failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
