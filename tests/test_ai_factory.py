"""
Test suite for AI Automation Factory.

This module contains tests for the core functionality of the AI Automation Factory.
"""
import pytest
import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from models.database import Base, get_db
from models.models import User, Task, Feedback
from config import settings

# Test database URL - use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine and session
engine = create_async_engine(TEST_DATABASE_URL, echo=True, future=True)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

# Fixture to create a test database session
@pytest.fixture(scope="function")
async def db_session():
    ""
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
@pytest.fixture(scope="function")
async def override_get_db(db_session):
    ""Override the get_db dependency for testing."""
    async def _override_get_db():
        try:
            yield db_session
        finally:
            pass  # Don't close the session here, let the fixture handle it
    
    return _override_get_db

# Fixture for the test client
@pytest.fixture(scope="function")
async def test_client(override_get_db):
    ""Create a test client with overridden dependencies."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

# Test cases
class TestTaskAPI:
    ""Test cases for the Task API endpoints."""
    
    async def test_create_task(self, test_client, db_session):
        ""Test creating a new task."""
        task_data = {
            "name": "Test Task",
            "description": "This is a test task",
            "priority": "normal"
        }
        
        response = test_client.post("/tasks/", json=task_data)
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["name"] == task_data["name"]
        assert data["status"] == "pending"
        
        # Verify the task was saved to the database
        task = await db_session.get(Task, data["id"])
        assert task is not None
        assert task.name == task_data["name"]
    
    async def test_get_task(self, test_client, db_session):
        ""Test retrieving a task by ID."""
        # Create a test task
        task = Task(
            task_id="test_get_task_123",
            name="Test Get Task",
            status="pending"
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)
        
        # Test getting the task
        response = test_client.get(f"/tasks/{task.task_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["task_id"] == task.task_id
        assert data["name"] == task.name
        assert data["status"] == task.status
    
    async def test_list_tasks(self, test_client, db_session):
        ""Test listing all tasks."""
        # Create some test tasks
        tasks = [
            Task(task_id=f"task_{i}", name=f"Task {i}", status="pending")
            for i in range(5)
        ]
        db_session.add_all(tasks)
        await db_session.commit()
        
        # Test listing tasks
        response = test_client.get("/tasks/")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) >= 5  # Should include our 5 tasks plus any from fixtures
        assert any(task["name"] == "Task 0" for task in data)

class TestFeedbackSystem:
    ""Test cases for the feedback system."""
    
    async def test_submit_feedback(self, test_client, db_session):
        ""Test submitting feedback."""
        feedback_data = {
            "type": "rating",
            "task_id": "test_task_123",
            "content": {"score": 4},
            "user_id": 1
        }
        
        response = test_client.post("/feedback/", json=feedback_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "id" in data
        
        # Verify the feedback was saved
        feedback = await db_session.get(Feedback, data["id"])
        assert feedback is not None
        assert feedback.type == "rating"
        assert feedback.content["score"] == 4
    
    async def test_analyze_feedback(self, test_client, db_session):
        ""Test analyzing feedback."""
        # Create some test feedback
        feedback_items = [
            Feedback(
                type="rating",
                content={"score": score},
                created_at=datetime.utcnow() - timedelta(days=i)
            )
            for i, score in enumerate([5, 4, 3, 2, 1], 1)
        ]
        db_session.add_all(feedback_items)
        await db_session.commit()
        
        # Test analysis
        response = test_client.get("/feedback/analyze?days=30")
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] >= 5
        assert "avg_rating" in data
        assert 1 <= data["avg_rating"] <= 5

class TestFileOperations:
    ""Test cases for file operations."""
    
    async def test_upload_file(self, test_client, tmp_path):
        ""Test file upload functionality."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("This is a test file")
        
        # Test file upload
        with open(test_file, "rb") as f:
            response = test_client.post(
                "/files/upload",
                files={"file": ("test.txt", f, "text/plain")}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["name"] == "test.txt"
        assert data["size"] > 0
    
    async def test_download_file(self, test_client, tmp_path):
        ""Test file download functionality."""
        # First upload a file
        test_file = tmp_path / "test_download.txt"
        test_file.write_text("Download test content")
        
        with open(test_file, "rb") as f:
            upload_response = test_client.post(
                "/files/upload",
                files={"file": ("test_download.txt", f, "text/plain")}
            )
        
        file_id = upload_response.json()["id"]
        
        # Now download it
        response = test_client.get(f"/files/download/{file_id}")
        assert response.status_code == 200
        assert response.content == b"Download test content"

# Run the tests
if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main(["-v", "-s", __file__]))
