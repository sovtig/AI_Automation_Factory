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
from hyperbot_db import hyperbot_db
from hyperbot_ai import generate_response, ethical_check
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
    await hyperbot_db.init_db()
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

# HyperBot Models
class ChatRequest(BaseModel):
    user_id: str
    message: str

class ChatResponse(BaseModel):
    response: str
    timestamp: str

class RealityOutputRequest(BaseModel):
    spacetime_metrics: Dict[str, Any]

class TimelineAdjustRequest(BaseModel):
    delta_t: float  # in Planck times

# HyperBot Endpoints
@app.post("/hyperbot/chat", response_model=ChatResponse)
async def hyperbot_chat(request: ChatRequest, x_quantum_key: str = Form(..., alias="X-Quantum-Key")):
    if x_quantum_key != "quantum-key-secure":  # Simple check; in production, use proper validation
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Get conversation history
    history = await hyperbot_db.get_conversation_history(request.user_id)

    # Generate response with dynamic learning
    response_text = await generate_response(request.message, history)

    # Ethical check
    if not ethical_check(response_text):
        response_text = "I'm sorry, but I cannot provide that response as it may violate ethical guidelines."

    # Save conversation
    await hyperbot_db.save_conversation(request.user_id, request.message, response_text)

    return {"response": response_text, "timestamp": datetime.utcnow().isoformat()}

@app.get("/hyperbot/history/{user_id}")
async def get_history(user_id: str, x_quantum_key: str = Form(..., alias="X-Quantum-Key")):
    if x_quantum_key != "quantum-key-secure":
        raise HTTPException(status_code=401, detail="Invalid API key")

    history = await hyperbot_db.get_conversation_history(user_id)
    return {"history": history}

@app.post("/hyperbot/reality/output")
async def reality_output(request: RealityOutputRequest, x_quantum_key: str = Form(..., alias="X-Quantum-Key")):
    if x_quantum_key != "quantum-key-secure":
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Simulate reality output manipulation
    result = {
        "status": "success",
        "manipulated_metrics": request.spacetime_metrics,
        "simulation_note": "Quantum-classical hybrid simulation completed"
    }
    return result

@app.post("/hyperbot/timeline/adjust")
async def timeline_adjust(request: TimelineAdjustRequest, x_quantum_key: str = Form(..., alias="X-Quantum-Key")):
    if x_quantum_key != "quantum-key-secure":
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Simulate temporal adjustment
    result = {
        "status": "success",
        "adjusted_timeline": f"Adjusted by {request.delta_t} Planck times",
        "simulation_note": "Local spacetime geodesics controlled"
    }
    return result

# Serve frontend
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
