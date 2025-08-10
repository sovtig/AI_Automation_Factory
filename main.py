import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from config import settings
from models.database import init_db, get_db, database
from models.models import Task, TaskLog, TaskStatus, TaskPriority, Feedback, File as FileModel
from workflows.file_manager import FileManager
from workflows.task_manager import TaskManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("AI Automation Factory starting...")
    await init_db()
    asyncio.create_task(task_manager.start())
    yield
    # Shutdown
    logger.info("AI Automation Factory stopping...")
    await task_manager.stop()
    if not settings.is_testing:
        await file_manager.close()


app = FastAPI(title="AI Automation Factory", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

task_manager = TaskManager()
file_manager = FileManager(
    base_dir=str(settings.DATA_DIR)
)


# Pydantic Models
class TaskCreate(BaseModel):
    name: str
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.NORMAL
    metadata: Optional[Dict[str, Any]] = Field(None, alias='parameters')

    class Config:
        orm_mode = True
        allow_population_by_field_name = True


class TaskRead(BaseModel):
    id: int
    task_id: str
    name: str
    description: Optional[str] = None
    status: TaskStatus
    priority: TaskPriority
    progress: float
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        orm_mode = True


class FeedbackCreate(BaseModel):
    task_id: int
    user_id: Optional[int] = None
    type: str
    content: Dict[str, Any]


class FeedbackRead(BaseModel):
    id: int
    task_id: int
    user_id: Optional[int]
    type: str
    content: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class FileRead(BaseModel):
    id: int
    name: str
    path: str
    size: int
    mime_type: str

    class Config:
        orm_mode = True


# API Endpoints
@app.post("/tasks/", response_model=TaskRead, status_code=201)
async def create_task(task_create: TaskCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new task.
    """
    task = Task(
        **task_create.model_dump(exclude={"metadata"}),
        task_id=str(uuid.uuid4()),
        metadata_=task_create.metadata
    )
    
    log = TaskLog(
        task=task,
        level='info',
            message=f"Task '{task.name}' created with status '{TaskStatus.PENDING.value}'"
    )

    db.add(task)
    db.add(log)

    await db.commit()
    await db.refresh(task)

    # Example of how to add a real task to the manager
    # async def sample_task_func(some_param):
    #     logger.info(f"Executing sample task with param: {some_param}")
    #     await asyncio.sleep(2)
    #     return {"status": "completed", "param": some_param}
    #
    # task_manager.add_task(task, sample_task_func, task.metadata.get("some_param"))

    return task


@app.get("/tasks/", response_model=List[TaskRead])
async def get_tasks(db: AsyncSession = Depends(get_db)):
    """
    Retrieve all tasks.
    """
    result = await db.execute(select(Task))
    tasks = result.scalars().all()
    return tasks


@app.get("/tasks/{task_id}", response_model=TaskRead)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve a single task by its ID.
    """
    result = await db.execute(select(Task).where(Task.task_id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/feedback/", response_model=FeedbackRead, status_code=201)
async def create_feedback(feedback_create: FeedbackCreate, db: AsyncSession = Depends(get_db)):
    """
    Submit feedback for a task.
    """
    feedback = Feedback(**feedback_create.model_dump())
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return feedback


@app.get("/feedback/analyze")
async def analyze_feedback(days: int = 7, db: AsyncSession = Depends(get_db)):
    """
    Analyze feedback over a given period.
    """
    start_date = datetime.now() - timedelta(days=days)

    # Total feedback
    total_result = await db.execute(
        select(func.count(Feedback.id)).where(Feedback.created_at >= start_date)
    )
    total = total_result.scalar_one()

    # Average rating
    avg_rating_result = await db.execute(
        select(func.avg(Feedback.content["score"].as_float())).where(
            Feedback.type == "rating",
            Feedback.created_at >= start_date
        )
    )
    avg_rating = avg_rating_result.scalar_one_or_none() or 0

    return {"total": total, "avg_rating": avg_rating}


@app.post("/files/upload", response_model=FileRead)
async def upload_file(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """
    Upload a file.
    """
    try:
        content = await file.read()
        file_path = await file_manager.create_file(
            content,
            f"{uuid.uuid4()}_{file.filename}"
        )

        file_record = FileModel(
            name=file.filename,
            path=str(file_path),
            size=len(content),
            mime_type=file.content_type,
            is_public=False # Default to private
        )

        db.add(file_record)
        await db.commit()
        await db.refresh(file_record)

        return file_record
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {e}")


@app.get("/files/download/{file_id}")
async def download_file(file_id: int, db: AsyncSession = Depends(get_db)):
    """
    Download a file by its ID.
    """
    result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file_record = result.scalar_one_or_none()

    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = Path(file_record.path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(file_path, media_type=file_record.mime_type, filename=file_record.name)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
