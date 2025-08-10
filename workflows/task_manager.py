"""
Task Management System for AI Automation Factory
Handles task creation, prioritization, and execution
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable, Awaitable
import asyncio
from datetime import datetime
import logging
from loguru import logger

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class TaskPriority(int, Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class TaskResult:
    success: bool
    output: Any
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class Task:
    def __init__(
        self,
        task_id: str,
        func: Callable[..., Awaitable[Any]],
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
        dependencies: Optional[List['Task']] = None,
    ):
        self.task_id = task_id
        self.func = func
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.priority = priority
        self.max_retries = max_retries
        self.dependencies = dependencies or []
        self.status = TaskStatus.PENDING
        self.result: Optional[TaskResult] = None
        self.retry_count = 0
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.logger = logger.bind(task_id=task_id)

    async def execute(self) -> TaskResult:
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.utcnow()
        
        # Check dependencies first
        for dep in self.dependencies:
            if dep.status != TaskStatus.COMPLETED:
                return TaskResult(
                    success=False,
                    output=None,
                    error=RuntimeError(f"Dependency {dep.task_id} not completed"),
                    metadata={"dependency_failed": dep.task_id}
                )
        
        # Execute the task with retries
        last_error = None
        
        while self.retry_count <= self.max_retries:
            try:
                self.logger.info(f"Executing task {self.task_id} (attempt {self.retry_count + 1}/{self.max_retries + 1})")
                output = await self.func(*self.args, **self.kwargs)
                self.status = TaskStatus.COMPLETED
                self.completed_at = datetime.utcnow()
                self.result = TaskResult(success=True, output=output)
                return self.result
                
            except Exception as e:
                last_error = e
                self.retry_count += 1
                
                if self.retry_count <= self.max_retries:
                    self.status = TaskStatus.RETRYING
                    retry_delay = min(2 ** (self.retry_count - 1), 30)  # Exponential backoff, max 30s
                    self.logger.warning(
                        f"Task {self.task_id} failed (attempt {self.retry_count}/{self.max_retries}). "
                        f"Retrying in {retry_delay} seconds. Error: {str(e)}"
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    self.status = TaskStatus.FAILED
                    self.completed_at = datetime.utcnow()
                    self.result = TaskResult(
                        success=False,
                        output=None,
                        error=last_error,
                        metadata={
                            "attempts": self.retry_count,
                            "max_attempts": self.max_retries
                        }
                    )
                    return self.result

class TaskManager:
    def __init__(self, max_concurrent_tasks: int = 5):
        self.tasks: Dict[str, Task] = {}
        self.task_queue = asyncio.PriorityQueue()
        self.max_concurrent_tasks = max_concurrent_tasks
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.logger = logger.bind(component="TaskManager")
        self._is_running = False
        self._task_executors = set()

    def add_task(self, task: Task) -> str:
        """Add a task to the manager and return its ID."""
        if task.task_id in self.tasks:
            raise ValueError(f"Task with ID {task.task_id} already exists")
            
        self.tasks[task.task_id] = task
        # Priority queue uses a tuple where first element is the priority (lower is higher priority)
        self.task_queue.put_nowait((task.priority.value, task.task_id))
        self.logger.info(f"Added task {task.task_id} with priority {task.priority}")
        return task.task_id

    async def _execute_task(self, task_id: str):
        """Execute a single task."""
        task = self.tasks[task_id]
        async with self.semaphore:
            try:
                await task.execute()
                if task.status == TaskStatus.COMPLETED:
                    self.logger.info(f"Task {task_id} completed successfully")
                else:
                    self.logger.error(
                        f"Task {task_id} failed after {task.retry_count} attempts: "
                        f"{task.result.error if task.result else 'Unknown error'}"
                    )
            except Exception as e:
                self.logger.exception(f"Unexpected error in task {task_id}: {str(e)}")
                task.status = TaskStatus.FAILED
                task.result = TaskResult(
                    success=False,
                    output=None,
                    error=e
                )
            finally:
                self.task_queue.task_done()

    async def start(self):
        """Start the task manager and begin processing tasks."""
        if self._is_running:
            self.logger.warning("Task manager is already running")
            return
            
        self._is_running = True
        self.logger.info("Starting task manager")
        
        while self._is_running or not self.task_queue.empty():
            try:
                # Get the next task (blocking with timeout to allow for shutdown)
                try:
                    _, task_id = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                    
                task = self.tasks.get(task_id)
                if not task:
                    self.logger.warning(f"Task {task_id} not found")
                    continue
                    
                # Create a task to execute this task
                executor = asyncio.create_task(self._execute_task(task_id))
                self._task_executors.add(executor)
                executor.add_done_callback(self._task_done_callback)
                
            except Exception as e:
                self.logger.exception(f"Error in task manager loop: {str(e)}")
                await asyncio.sleep(1)  # Prevent tight loop on errors

    def _task_done_callback(self, task):
        """Clean up completed tasks."""
        self._task_executors.discard(task)
        try:
            task.result()  # Re-raise any exceptions from the task
        except Exception as e:
            self.logger.error(f"Error in task executor: {str(e)}")

    async def stop(self):
        """Stop the task manager gracefully."""
        self.logger.info("Stopping task manager")
        self._is_running = False
        
        # Wait for all tasks to complete
        await self.task_queue.join()
        
        # Cancel any running executors
        for executor in self._task_executors:
            executor.cancel()
            
        # Wait for all executors to complete
        if self._task_executors:
            await asyncio.wait(self._task_executors, return_when=asyncio.ALL_COMPLETED)
            
        self.logger.info("Task manager stopped")

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a task."""
        task = self.tasks.get(task_id)
        if not task:
            return None
            
        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "priority": task.priority.name,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "retry_count": task.retry_count,
            "max_retries": task.max_retries,
            "result": {
                "success": task.result.success if task.result else None,
                "error": str(task.result.error) if task.result and task.result.error else None,
                "metadata": task.result.metadata if task.result else {}
            } if task.result else None
        }
