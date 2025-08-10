"""
AI Automation Factory - Main Application

FastAPI-based web interface for the AI Automation Factory.
"""
import os
import uvicorn
from fastapi import FastAPI, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid
import asyncio
from datetime import datetime

from workflows.task_manager import Task, TaskManager, TaskPriority, TaskStatus
from workflows.file_manager import FileManager
from loguru import logger
import sys

# Configure logging
logger.remove()
logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
logger.add("logs/ai_factory.log", rotation="100 MB", retention="7 days")

# Create logs directory
Path("logs").mkdir(exist_ok=True)

# Initialize components
app = FastAPI(title="AI Automation Factory", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

task_manager = TaskManager(max_concurrent_tasks=5)
file_manager = FileManager()

# Models
class TaskRequest(BaseModel):
    task_type: str
    parameters: Dict[str, Any] = {}
    priority: TaskPriority = TaskPriority.NORMAL

class TaskResponse(BaseModel):
    task_id: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# Startup/shutdown events
@app.on_event("startup")
async def startup():
    asyncio.create_task(task_manager.start())
    logger.info("AI Automation Factory started")

@app.on_event("shutdown")
async def shutdown():
    await task_manager.stop()
    await file_manager.close()
    logger.info("AI Automation Factory stopped")

# API Endpoints
@app.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(task_request: TaskRequest):
    task_id = str(uuid.uuid4())
    
    async def task_handler(parameters: Dict[str, Any]):
        # Example task handler
        await asyncio.sleep(1)  # Simulate work
        return {"result": "Task completed", "parameters": parameters}
    
    task = Task(
        task_id=task_id,
        func=task_handler,
        kwargs={"parameters": task_request.parameters},
        priority=task_request.priority
    )
    
    task_manager.add_task(task)
    return {"task_id": task_id, "status": task.status.value, "created_at": task.created_at.isoformat()}

@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    task_info = task_manager.get_task_status(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_info

@app.post("/files/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        file_path = await file_manager.create_file(
            content.decode('utf-8'),
            f"{uuid.uuid4()}_{file.filename}"
        )
        return {"filename": file.filename, "path": str(file_path)}
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
