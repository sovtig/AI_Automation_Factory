"""
HyperBot Database Module

Handles database operations for HyperBot's digital memory.
"""
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
import asyncio

class HyperBotDB:
    """Database handler for HyperBot conversations."""

    def __init__(self, db_path: str = "./data/hyperbot.db"):
        self.db_path = db_path

    async def init_db(self):
        """Initialize the database and create tables if they don't exist."""
        def _init():
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    userId TEXT NOT NULL,
                    input TEXT NOT NULL,
                    response TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()
            conn.close()

        await asyncio.get_event_loop().run_in_executor(None, _init)
        print("HyperBot database initialized")

    async def save_conversation(self, user_id: str, user_input: str, response: str):
        """Save a conversation to the database."""
        timestamp = datetime.utcnow().isoformat()

        def _save():
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO conversations (userId, input, response, timestamp) VALUES (?, ?, ?, ?)",
                (user_id, user_input, response, timestamp)
            )
            conn.commit()
            conn.close()

        await asyncio.get_event_loop().run_in_executor(None, _save)
        print(f"Saved conversation for user {user_id}")

    async def get_conversation_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve conversation history for a user."""
        def _get():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "SELECT id, input, response, timestamp FROM conversations WHERE userId = ? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit)
            )
            rows = cursor.fetchall()
            conn.close()
            return rows

        rows = await asyncio.get_event_loop().run_in_executor(None, _get)

        # Convert to list of dicts
        history = [
            {
                "id": row[0],
                "input": row[1],
                "response": row[2],
                "timestamp": row[3]
            }
            for row in rows
        ]
        return history

# Global instance
hyperbot_db = HyperBotDB()