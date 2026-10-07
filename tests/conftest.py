import asyncio
import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.db.models import Base

# Real PostgreSQL 16 test database URL
TEST_PG_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres@127.0.0.1:5433/resort_voice_test"
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def pg_engine():
    """Async engine fixture connected to real PostgreSQL 16."""
    from app.db.session import engine
    yield engine



@pytest_asyncio.fixture(scope="function")
async def pg_session(pg_engine):
    """Async session fixture connected to real PostgreSQL 16."""
    session_factory = async_sessionmaker(
        bind=pg_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def rollback_session(pg_engine):
    """
    Isolated transaction rollback fixture:
    Opens a connection to PostgreSQL, begins an outer transaction, binds an
    AsyncSession, yields the session for test execution, and rolls back the
    entire transaction in finally. Zero test rows are ever persisted.
    """
    async with pg_engine.connect() as conn:
        trans = await conn.begin()
        session_factory = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False
        )
        async with session_factory() as session:
            try:
                yield session
            finally:
                if trans.is_active:
                    await trans.rollback()


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_engine():
    """Ensure global async engine connections do not cross test event loops."""
    yield
    from app.db.session import engine
    await engine.dispose()

