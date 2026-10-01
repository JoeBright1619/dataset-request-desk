"""CLI entry point for the app.cli module.

Allows running commands like:
    python -m app.cli seed-users
"""

import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.cli <command>")
        print("Available commands:")
        print("  seed-users    Create initial users (idempotent)")
        sys.exit(1)

    command = sys.argv[1]

    if command == "seed-users":
        import asyncio

        from app.cli.seed_users import main

        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
