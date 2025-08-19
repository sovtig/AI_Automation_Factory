import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy import select

from main import app
from models.database import database, Base, get_db
from models.models import Task
from workflows.task_manager import TaskManager

# Use an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Override the database dependency for testing
@pytest.fixture(scope="session", autouse=True)
def override_database():
    """
    Fixture to override the global database object for the entire test session.
    """
    # Keep the original database object
    original_database = database

    # Create a new database object for testing
    test_database = type(database)(url=TEST_DATABASE_URL, poolclass=NullPool)

    # Monkeypatch the database object in the models.database module
    import models.database
    models.database.database = test_database

    # Also monkeypatch the task_manager in main to use the test database
    import main
    main.app_state["task_manager"] = TaskManager(
        max_concurrent_tasks=5, db_session_factory=test_database.session_factory
    )

    yield

    # Restore the original database object
    models.database.database = original_database

@pytest_asyncio.fixture(scope="function", autouse=True)
async def db_session(override_database):
    """
    Fixture to create and drop tables for each test function.
    """
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def client(db_session) -> AsyncClient:
    """
    Create a new test client for each test function.
    """
    # Override the get_db dependency to use the test database
    app.dependency_overrides[get_db] = database.session

    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

@pytest.mark.asyncio
async def test_create_task(client: AsyncClient):
    """Test creating a new task."""
    task_data = {
        "task_type": "example",
        "parameters": {"param1": "value1"},
    }
    
    response = await client.post("/tasks", json=task_data)
    
    assert response.status_code == 201
    data = response.json()
    
    assert "task_id" in data
    assert data["status"] == "pending"
    
    # Verify the task was saved to the database
    task_id = data["task_id"]
    async with database.session() as session:
        result = await session.execute(select(Task).where(Task.task_id == task_id))
        db_task = result.scalar_one_or_none()
        assert db_task is not None
        assert db_task.status.value == "pending"

@pytest.mark.asyncio
async def test_get_task(client: AsyncClient):
    """Test retrieving a task by ID."""
    # First, create a task
    task_data = {
        "task_type": "example_for_get",
        "parameters": {"param1": "value1"},
    }
    response = await client.post("/tasks", json=task_data)
    assert response.status_code == 201
    created_task = response.json()
    task_id = created_task["task_id"]

    # Now, get the task from the task manager
    response = await client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["task_id"] == task_id
    assert data["status"] == "pending"
