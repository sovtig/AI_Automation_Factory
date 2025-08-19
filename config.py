"""
Configuration settings for the AI Automation Factory.

This module handles all configuration settings using environment variables
with sensible defaults.
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from pydantic import Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings
from enum import Enum
from loguru import logger
import logging

class EnvironmentType(str, Enum):
    """Application environment types."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"

class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class Settings(BaseSettings):
    """Application settings."""
    
    # Application settings
    APP_NAME: str = "AI Automation Factory"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: EnvironmentType = EnvironmentType.DEVELOPMENT
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-here"  # Change in production!
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    RELOAD: bool = True
    
    # CORS settings
    CORS_ORIGINS: List[str] = ["*"]
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]
    
    # Database settings
    DATABASE_URL: str = "sqlite+aiosqlite:///./ai_factory.db"
    TEST_DATABASE_URL: str = "sqlite+aiosqlite:///./test_ai_factory.db"
    
    # File storage
    BASE_DIR: Path = Path(__file__).parent
    DATA_DIR: Path = BASE_DIR / "data"
    UPLOAD_DIR: Path = DATA_DIR / "uploads"
    OUTPUT_DIR: Path = DATA_DIR / "outputs"
    TEMP_DIR: Path = DATA_DIR / "temp"
    
    # Logging
    LOG_LEVEL: LogLevel = LogLevel.INFO
    LOG_FORMAT: str = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    LOG_FILE: Optional[Path] = DATA_DIR / "logs" / "app.log"
    LOG_ROTATION: str = "100 MB"
    LOG_RETENTION: str = "7 days"
    
    # AI Model settings
    DEFAULT_AI_MODEL: str = "gpt-4-turbo"
    AI_API_KEY: Optional[str] = None
    AI_MAX_TOKENS: int = 2000
    AI_TEMPERATURE: float = 0.7
    
    # Google Drive settings
    GOOGLE_DRIVE_ENABLED: bool = False
    GOOGLE_DRIVE_CREDENTIALS_FILE: Optional[Path] = None
    GOOGLE_DRIVE_TOKEN_FILE: Optional[Path] = None
    GOOGLE_DRIVE_ROOT_FOLDER_ID: Optional[str] = None
    
    # Task settings
    MAX_CONCURRENT_TASKS: int = 5
    TASK_TIMEOUT: int = 300  # 5 minutes
    TASK_RETRY_ATTEMPTS: int = 3
    
    # Security
    API_KEY_HEADER: str = "X-API-Key"
    RATE_LIMIT: str = "100/minute"
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    @field_validator("DATA_DIR", "UPLOAD_DIR", "OUTPUT_DIR", "TEMP_DIR", mode="before")
    def create_data_dirs(cls, v: Any) -> Path:
        """Create data directories if they don't exist."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @model_validator(mode="after")
    def handle_paths(self) -> "Settings":
        # log file
        if self.LOG_FILE is not None:
            self.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        # google drive credentials
        if self.GOOGLE_DRIVE_CREDENTIALS_FILE is not None:
            path = Path(self.GOOGLE_DRIVE_CREDENTIALS_FILE)
            if not path.is_absolute():
                path = self.BASE_DIR / path
            if path.exists() and "credentials" in path.name and path.suffix == ".json":
                self.GOOGLE_DRIVE_CREDENTIALS_FILE = path

        if self.GOOGLE_DRIVE_TOKEN_FILE is not None:
            path = Path(self.GOOGLE_DRIVE_TOKEN_FILE)
            if not path.is_absolute():
                path = self.BASE_DIR / path
            self.GOOGLE_DRIVE_TOKEN_FILE = path

        return self
    
    def configure_logging(self) -> None:
        """Configure logging based on settings."""
        import sys
        from loguru import logger
        
        # Remove default handler
        logger.remove()
        
        # Add console handler
        logger.add(
            sys.stderr,
            level=self.LOG_LEVEL,
            format=self.LOG_FORMAT,
            backtrace=self.DEBUG,
            diagnose=self.DEBUG
        )
        
        # Add file handler if configured
        if self.LOG_FILE:
            logger.add(
                str(self.LOG_FILE),
                level=self.LOG_LEVEL,
                format=self.LOG_FORMAT,
                rotation=self.LOG_ROTATION,
                retention=self.LOG_RETENTION,
                backtrace=self.DEBUG,
                diagnose=self.DEBUG
            )
        
        # Set log level for third-party libraries
        logging.getLogger().setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        
        logger.info(f"Logging configured with level {self.LOG_LEVEL}")
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == EnvironmentType.PRODUCTION
    
    @property
    def is_testing(self) -> bool:
        """Check if running in test environment."""
        return self.ENVIRONMENT == EnvironmentType.TESTING
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == EnvironmentType.DEVELOPMENT
    
    def get_database_url(self) -> str:
        """Get the appropriate database URL based on environment."""
        if self.is_testing and self.TEST_DATABASE_URL:
            return str(self.TEST_DATABASE_URL)
        return str(self.DATABASE_URL) if self.DATABASE_URL else ""

# Create settings instance
settings = Settings()

# Configure logging when module is imported
settings.configure_logging()
