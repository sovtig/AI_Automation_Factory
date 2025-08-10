from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings
from typing import AsyncGenerator

# Create an async engine
engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)

# Create a configured "Session" class
AsyncSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

# Create a base class for declarative models
Base = declarative_base()

# Global database object (optional, but can be useful for scripts)
class DB:
    def __init__(self):
        self.session_factory = AsyncSessionLocal
        self.engine = engine

    @property
    async def session(self) -> AsyncSession:
        return self.session_factory()

database = DB()

async def init_db():
    """Initialize the database and create tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency to get a DB session."""
    async with AsyncSessionLocal() as session:
        yield session
