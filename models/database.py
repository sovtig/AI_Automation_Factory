"""
Database module for AI Automation Factory.

Provides database connection and session management using SQLAlchemy with async support.
"""
import logging
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from config import settings
from loguru import logger

# Create base class for models
Base = declarative_base()

class Database:
    """Database connection and session management."""
    
    def __init__(self, url: Optional[str] = None, **kwargs):
        """Initialize the database connection.
        
        Args:
            url: Database connection URL. If not provided, uses settings.DATABASE_URL.
            **kwargs: Additional arguments to pass to create_async_engine.
        """
        self._engine = None
        self._session_factory = None
        self._url = url or settings.get_database_url()
        self._kwargs = kwargs
        self.logger = logger.bind(component="Database")
    
    @property
    def engine(self):
        """Get the SQLAlchemy async engine, creating it if necessary."""
        if self._engine is None:
            self.logger.info(f"Creating database engine for {self._url}")
            self._engine = create_async_engine(
                self._url,
                echo=settings.DEBUG,
                pool_pre_ping=True,
                pool_recycle=300,  # Recycle connections after 5 minutes
                **self._kwargs
            )
        return self._engine
    
    @property
    def session_factory(self):
        """Get the async session factory."""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False
            )
        return self._session_factory
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.session_factory()
        try:
            self.logger.debug("Database session started")
            yield session
            await session.commit()
            self.logger.debug("Database session committed")
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            await session.rollback()
            raise
        finally:
            await session.close()
            self.logger.debug("Database session closed")
    
    async def create_all(self):
        """Create all database tables."""
        self.logger.info("Creating database tables")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def drop_all(self):
        """Drop all database tables."""
        self.logger.warning("Dropping all database tables")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    async def dispose(self):
        """Dispose of the database connection pool."""
        if self._engine:
            self.logger.info("Disposing database engine")
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

# Create a global database instance
database = Database()

# Import models to ensure they are registered with SQLAlchemy
# This must be done after the Base is created and before the tables are created
# to avoid circular imports
from . import models  # noqa: F401

# Shortcut for getting a database session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async DB session."""
    async with database.session() as session:
        yield session
