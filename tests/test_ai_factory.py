"""
Test suite for AI Automation Factory.

This module contains tests for the core functionality of the AI Automation Factory.
"""
import pytest
import pytest_asyncio
import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from models.database import Base, get_db
from models.models import User, Task, Feedback
from config import settings, EnvironmentType

# Test cases
class TestTaskAPI:
    """Test cases for the Task API endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_task(self, test_client, db_session):
        """Test creating a new task."""
        task_data = {
            "name": "Test Task",
            "description": "This is a test task",
            "priority": 2,  # Use integer value for TaskPriority.NORMAL
            "parameters": {}
        }
        
        response = test_client.post("/tasks/", json=task_data)
        assert response.status_code == 201
        data = response.json()
        
        assert "task_id" in data
        assert data["name"] == task_data["name"]
        assert data["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_get_task(self, test_client, db_session):
        """Test retrieving a task by ID."""
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
    
    @pytest.mark.asyncio
    async def test_list_tasks(self, test_client, db_session):
        """Test listing all tasks."""
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
        
        assert len(data) >= 6  # Should include our 5 tasks plus the one from the fixture
        assert any(task["name"] == "Task 0" for task in data)

class TestFeedbackSystem:
    """Test cases for the feedback system."""
    
    @pytest.mark.asyncio
    async def test_submit_feedback(self, test_client, db_session):
        """Test submitting feedback."""
        # Get the task created by the fixture
        task_result = await db_session.execute(select(Task).where(Task.task_id == "test_task_123"))
        task = task_result.scalar_one()

        feedback_data = {
            "type": "rating",
            "task_id": task.id,
            "content": {"score": 4},
            "user_id": 1
        }
        
        response = test_client.post("/feedback/", json=feedback_data)
        assert response.status_code == 201
        data = response.json()
        
        assert data["type"] == feedback_data["type"]
        assert data["task_id"] == feedback_data["task_id"]
        assert data["content"]["score"] == 4
        
    
    @pytest.mark.asyncio
    async def test_analyze_feedback(self, test_client, db_session):
        """Test analyzing feedback."""
        # Create some test feedback
        task = await db_session.get(Task, 1)
        feedback_items = [
            Feedback(
                task_id=task.id,
                user_id=1,
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
    """Test cases for file operations."""
    
    @pytest.mark.asyncio
    async def test_upload_file(self, test_client, tmp_path):
        """Test file upload functionality."""
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
    
    @pytest.mark.asyncio
    async def test_download_file(self, test_client, tmp_path):
        """Test file download functionality."""
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
