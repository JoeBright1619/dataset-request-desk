"""CLI entry point for the app.cli module.

Allows running commands like:
    python -m app.cli seed-users
    python -m app.cli import-episodes <file_path>
"""

import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.cli <command> [args...]")
        print("Available commands:")
        print("  seed-users        Create initial users (idempotent)")
        print("  import-episodes   Import episodes from a CSV file")
        sys.exit(1)

    command = sys.argv[1]

    if command == "seed-users":
        import asyncio

        from app.cli.seed_users import main as seed_users_main

        exit_code = asyncio.run(seed_users_main())
        sys.exit(exit_code)
    elif command == "import-episodes":
        import asyncio

        from app.cli.import_episodes import main as import_episodes_main

        exit_code = asyncio.run(import_episodes_main(sys.argv[2:]))
        sys.exit(exit_code)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
