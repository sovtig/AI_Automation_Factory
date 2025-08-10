import pytest
from sqlalchemy import select
from models.models import APILog

class TestLoggingMiddleware:
    """Test cases for the API Logging Middleware."""

    @pytest.mark.asyncio
    async def test_api_log_created(self, test_client, db_session):
        """Test that a log is created for a simple GET request."""
        # Make a request to a known endpoint
        response = test_client.get("/tasks/")
        assert response.status_code == 200

        # Check that a log entry was created
        result = await db_session.execute(select(APILog))
        logs = result.scalars().all()

        assert len(logs) == 1
        log_entry = logs[0]

        assert log_entry.method == "GET"
        assert log_entry.path == "/tasks/"
        assert log_entry.status_code == 200
        assert log_entry.client_host == "testclient"
        assert log_entry.process_time > 0
