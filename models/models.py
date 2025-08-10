"""
Database models for AI Automation Factory.

This module defines the SQLAlchemy models for the application.
"""
from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional, Dict, Any

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    JSON,
    Enum,
    Table,
    func,
    event
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

from config import settings
from .database import Base

# Association tables
user_role = Table(
    'user_role',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'))
)

task_dependency = Table(
    'task_dependency',
    Base.metadata,
    Column('task_id', Integer, ForeignKey('tasks.id', ondelete='CASCADE')),
    Column('depends_on_id', Integer, ForeignKey('tasks.id', ondelete='CASCADE'))
)

class User(AsyncAttrs, Base):
    """User model for authentication and authorization."""
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    roles: Mapped[List['Role']] = relationship('Role', secondary=user_role, back_populates='users')
    tasks: Mapped[List['Task']] = relationship('Task', back_populates='owner')
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"

class Role(AsyncAttrs, Base):
    """Role model for role-based access control."""
    __tablename__ = 'roles'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Relationships
    users: Mapped[List['User']] = relationship('User', secondary=user_role, back_populates='roles')
    permissions: Mapped[List['Permission']] = relationship('Permission', back_populates='role')
    
    def __repr__(self):
        return f"<Role(id={self.id}, name='{self.name}')>"

class Permission(AsyncAttrs, Base):
    """Permission model for fine-grained access control."""
    __tablename__ = 'permissions'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey('roles.id', ondelete='CASCADE'))
    
    # Relationships
    role: Mapped['Role'] = relationship('Role', back_populates='permissions')
    
    def __repr__(self):
        return f"<Permission(id={self.id}, name='{self.name}', resource='{self.resource}', action='{self.action}')>"

class TaskStatus(str, PyEnum):
    """Status of a task."""
    PENDING = 'pending'
    QUEUED = 'queued'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    RETRYING = 'retrying'

class TaskPriority(int, PyEnum):
    """Priority of a task."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

class Task(AsyncAttrs, Base):
    """Task model for background job processing."""
    __tablename__ = 'tasks'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    priority: Mapped[TaskPriority] = mapped_column(Enum(TaskPriority), default=TaskPriority.NORMAL, nullable=False)
    progress: Mapped[float] = mapped_column(default=0.0, nullable=False)
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column('metadata', JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    timeout: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # in seconds
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    
    # Relationships
    owner: Mapped[Optional['User']] = relationship('User', back_populates='tasks')
    dependencies: Mapped[List['Task']] = relationship(
        'Task',
        secondary=task_dependency,
        primaryjoin=(id == task_dependency.c.task_id),
        secondaryjoin=(id == task_dependency.c.depends_on_id),
        backref='dependents'
    )
    logs: Mapped[List['TaskLog']] = relationship('TaskLog', back_populates='task', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Task(id={self.id}, task_id='{self.task_id}', name='{self.name}', status='{self.status}')>"

class TaskLog(AsyncAttrs, Base):
    """Log entries for tasks."""
    __tablename__ = 'task_logs'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)  # 'info', 'warning', 'error', 'debug'
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column('metadata', JSON, nullable=True)
    
    # Relationships
    task: Mapped['Task'] = relationship('Task', back_populates='logs')
    
    def __repr__(self):
        return f"<TaskLog(id={self.id}, task_id={self.task_id}, level='{self.level}', message='{self.message[:50]}...')>"

class File(AsyncAttrs, Base):
    """File model for tracking uploaded and generated files."""
    __tablename__ = 'files'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)  # in bytes
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    hash: Mapped[Optional[str]] = mapped_column(String(64))  # SHA-256 hash of file content
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column('metadata', JSON, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    
    # Relationships
    owner: Mapped[Optional['User']] = relationship('User')
    
    def __repr__(self):
        return f"<File(id={self.id}, name='{self.name}', path='{self.path}')>"

class APILog(AsyncAttrs, Base):
    """Log of API requests and responses."""
    __tablename__ = 'api_logs'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    client_host: Mapped[str] = mapped_column(String(50), nullable=False)
    process_time: Mapped[float] = mapped_column(Float, nullable=False)  # in seconds
    request_headers: Mapped[Dict[str, str]] = mapped_column(JSON, nullable=True)
    response_headers: Mapped[Dict[str, str]] = mapped_column(JSON, nullable=True)
    request_body: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    response_body: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user: Mapped[Optional['User']] = relationship('User')
    
    def __repr__(self):
        return f"<APILog(id={self.id}, {self.method} {self.path} {self.status_code})>"

# Event listeners
@event.listens_for(Task, 'after_insert')
def task_after_insert(mapper, connection, task):
    """Log task creation."""
    from .database import database
    
    async def log_task_creation():
        async with database.session() as session:
            log = TaskLog(
                task_id=task.id,
                level='info',
                message=f"Task '{task.name}' created with status '{task.status}'"
            )
            session.add(log)
            await session.commit()
    
    asyncio.create_task(log_task_creation())

@event.listens_for(Task, 'after_update')
def task_after_update(mapper, connection, task):
    """Log task status changes."""
    from .database import database
    
    # Get the previous state of the task
    history = inspect(task).attrs
    status_history = history.status.history
    
    # Only log if status has changed
    if status_history.has_changes():
        old_status = status_history.deleted[0] if status_history.deleted else None
        new_status = task.status
        
        async def log_status_change():
            async with database.session() as session:
                log = TaskLog(
                    task_id=task.id,
                    level='info',
                    message=f"Task status changed from '{old_status}' to '{new_status}'"
                )
                session.add(log)
                await session.commit()
        
        asyncio.create_task(log_status_change())
