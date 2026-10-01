"""
Pytest configuration and shared fixtures.
"""

import pytest
import pytest_asyncio
from app.core.config import settings
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


test_engine = create_async_engine(
    settings.database_url,
    echo=False,
    poolclass=NullPool,
)

TestSessionFactory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Transactional session; everything is rolled back at teardown."""
    connection = await test_engine.connect()
    transaction = await connection.begin()

    session = TestSessionFactory(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        await session.close()
        if transaction.is_active:
            await transaction.rollback()
        await connection.close()
