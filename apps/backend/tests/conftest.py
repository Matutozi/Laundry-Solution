import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401 — register all models with Base.metadata
from app.database import Base, get_session
from app.dependencies.queue import get_task_queue
from app.main import app as fastapi_app
from app.queue import MemoryTaskQueue

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://ghebee:wisewash@127.0.0.1:5432/wisewash_test",
)

# NullPool prevents connections from being reused across event loops
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

# Module-level queue shared across all tests — cleared per test via fake_queue fixture
_test_queue = MemoryTaskQueue()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # sync_global_seq is not part of SQLAlchemy metadata — create it explicitly
        await conn.execute(text(
            "CREATE SEQUENCE IF NOT EXISTS sync_global_seq START 1 INCREMENT 1"
        ))
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP SEQUENCE IF EXISTS sync_global_seq"))


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    async with test_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def fake_queue() -> MemoryTaskQueue:
    """Return the shared test queue after clearing it. Use in tests that inspect enqueued jobs."""
    _test_queue.clear()
    return _test_queue


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    async def override_get_session():
        yield db_session

    fastapi_app.dependency_overrides[get_session] = override_get_session
    fastapi_app.dependency_overrides[get_task_queue] = lambda: _test_queue

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()
