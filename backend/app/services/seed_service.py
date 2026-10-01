"""Seed service for creating initial users.

Idempotent seeding: running multiple times does not create duplicates.
"""

import json
import logging
from pathlib import Path
from typing import Any, TypedDict, cast

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = logging.getLogger(__name__)


class SeedUser(TypedDict, total=False):
    email: str
    password: str
    role: str
    name: str
    organisation: str


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def load_seed_users() -> list[SeedUser]:
    """Load seed users from seed/users.json."""
    seed_file = Path(__file__).parent.parent.parent.parent / "seed" / "users.json"

    if not seed_file.exists():
        logger.warning(f"Seed file not found: {seed_file}")
        return []

    with open(seed_file, encoding="utf-8") as f:
        data: Any = json.load(f)

    return cast(list[SeedUser], data)


async def seed_users(session: AsyncSession) -> dict[str, int]:
    """Seed initial users if they don't exist.

    Args:
        session: Database session

    Returns:
        Dictionary with counts: {"created": N, "existing": N}
    """
    created = 0
    existing = 0

    seed_users_data = load_seed_users()

    if not seed_users_data:
        logger.warning("No seed users loaded")
        return {"created": 0, "existing": 0}

    for seed_user in seed_users_data:
        # Check if user already exists
        stmt = select(User).where(User.email == seed_user["email"])
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is not None:
            logger.info(f"User '{seed_user['email']}' already exists, skipping")
            existing += 1
            continue

        # Create new user
        new_user = User(
            email=seed_user["email"],
            password_hash=hash_password(seed_user["password"]),
            role=seed_user["role"],
            name=seed_user["name"],
            organisation=seed_user.get("organisation"),  # Optional field
            is_active=True,
        )
        session.add(new_user)
        created += 1
        logger.info(
            f"Created seed user: {seed_user['email']} "
            f"(role: {seed_user['role']}, name: {seed_user['name']})"
        )
    await session.commit()

    return {"created": created, "existing": existing}
