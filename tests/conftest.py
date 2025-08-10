import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from models.database import Base, get_db, database
from models.models import User, Task
from config import settings, EnvironmentType

# Test database URL - use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine and session
engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

# Fixture to create a test database session
@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Create a new database session for testing.

    This fixture creates all tables, yields a session for testing,
    then drops all tables after the test is complete.
    """
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create a new session
    async with TestingSessionLocal() as session:
        # Add test data
        test_user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_test_password",
            is_active=True
        )
        session.add(test_user)
        await session.commit()
        await session.refresh(test_user)

        # Create test task
        test_task = Task(
            task_id="test_task_123",
            name="Test Task",
            status="pending",
            owner_id=test_user.id
        )
        session.add(test_task)
        await session.commit()

        yield session

    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

# Fixture to override the get_db dependency in FastAPI
@pytest_asyncio.fixture(scope="function")
async def override_get_db(db_session):
    """Override the get_db dependency for testing."""
    async def _override_get_db():
        yield db_session

    return _override_get_db

# Fixture for the test client
@pytest.fixture(scope="function")
def test_client(override_get_db):
    """Create a test client with overridden dependencies."""
    original_env = settings.ENVIRONMENT
    settings.ENVIRONMENT = EnvironmentType.TESTING

    # Monkey-patch the global database object for middleware
    original_engine = database.engine
    original_session_factory = database.session_factory
    database.engine = engine
    database.session_factory = TestingSessionLocal

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client

    # Restore original settings
    settings.ENVIRONMENT = original_env
    app.dependency_overrides.clear()
    database.engine = original_engine
    database.session_factory = original_session_factory
