"""
Setup script for AI Automation Factory

This script handles installation and configuration of all components.
"""
import os
import sys
import json
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configuration
REQUIRED_PYTHON = (3, 9)
REQUIRED_PACKAGES = [
    'aiofiles>=0.8.0',
    'aiosqlite>=0.17.0',
    'beautifulsoup4>=4.11.1',
    'fastapi>=0.85.0',
    'google-api-python-client>=2.48.0',
    'google-auth-oauthlib>=1.0.0',
    'loguru>=0.6.0',
    'numpy>=1.23.3',
    'pandas>=1.5.0',
    'pillow>=9.2.0',
    'prometheus-client>=0.15.0',
    'psutil>=5.9.3',
    'pydantic>=1.10.2',
    'pytest>=7.1.3',
    'pytest-asyncio>=0.19.0',
    'python-dotenv>=0.21.0',
    'pytesseract>=0.3.9',
    'pywin32>=305; sys_platform == "win32"',
    'pyyaml>=6.0',
    'requests>=2.28.1',
    'setuptools>=65.5.0',
    'typer>=0.7.0',
    'uvicorn>=0.19.0',
    'watchdog>=2.1.9',
]

# Directories to create
DIRECTORIES = [
    'config',
    'data',
    'data/sync',
    'data/processed',
    'data/backup',
    'logs',
    'scripts',
    'tests',
]

# Configuration templates
CONFIG_TEMPLATE = {
    "version": "1.0",
    "accounts": [
        {
            "name": "xy_drive_3",
            "credentials_file": "credentials_xy3.json",
            "token_file": "token_xy3.json",
            "description": "XYDrive 3 - Main Storage",
            "priority": 1,
            "quota_warning_threshold": 0.8
        },
        {
            "name": "xy_drive_4",
            "credentials_file": "credentials_xy4.json",
            "token_file": "token_xy4.json",
            "description": "XYDrive 4 - Backup Storage",
            "priority": 2,
            "quota_warning_threshold": 0.8
        }
    ],
    "default_account": "xy_drive_3",
    "sync_folders": [
        {
            "name": "xy3_documents",
            "local_path": "./data/sync/xy3/documents",
            "drive_folder_id": "FOLDER_ID_XY3_DOCS",
            "account": "xy_drive_3",
            "sync_interval": 3600,
            "file_patterns": ["*.pdf", "*.docx", "*.xlsx", "*.pptx"],
            "exclude_patterns": ["*.tmp"],
            "max_file_size_mb": 100,
            "retry_attempts": 3,
            "retry_delay_seconds": 5
        },
        {
            "name": "xy3_images",
            "local_path": "./data/sync/xy3/images",
            "drive_folder_id": "FOLDER_ID_XY3_IMAGES",
            "account": "xy_drive_3",
            "sync_interval": 7200,
            "file_patterns": ["*.jpg", "*.jpeg", "*.png", "*.gif"],
            "max_file_size_mb": 50,
            "compress_images": True,
            "compression_quality": 85
        },
        {
            "name": "xy4_backup",
            "local_path": "./data/sync/xy4/backup",
            "drive_folder_id": "FOLDER_ID_XY4_BACKUP",
            "account": "xy_drive_4",
            "sync_interval": 86400,
            "backup_retention_days": 30,
            "verify_backup_integrity": True
        },
        {
            "name": "xy4_archives",
            "local_path": "./data/sync/xy4/archives",
            "drive_folder_id": "FOLDER_ID_XY4_ARCHIVES",
            "account": "xy_drive_4",
            "sync_interval": 43200,
            "file_patterns": ["*.zip", "*.rar", "*.7z"],
            "extract_archives": True,
            "delete_after_extraction": False
        }
    ],
    "watch_directories": [
        {
            "path": "./data/sync/xy3/documents",
            "account": "xy_drive_3",
            "recursive": True,
            "patterns": ["*.pdf", "*.docx", "*.xlsx", "*.pptx", "*.jpg", "*.jpeg", "*.png"],
            "ignore_patterns": ["*.tmp", "~*"],
            "cooldown": 5.0,
            "process_existing": True,
            "move_processed": "./data/processed"
        }
    ],
    "system_service": {
        "enabled": True,
        "service_name": "AIFactoryDriveSync",
        "display_name": "AI Factory Drive Sync Service",
        "description": "Manages synchronization between local files and Google Drive accounts",
        "startup_type": "auto",
        "log_level": "INFO",
        "log_retention_days": 7,
        "max_log_size_mb": 10,
        "watchdog": {
            "enabled": True,
            "check_interval_seconds": 60,
            "max_restarts": 3
        },
        "notifications": {
            "email": {
                "enabled": False,
                "smtp_server": "smtp.example.com",
                "smtp_port": 587,
                "username": "user@example.com",
                "password_env": "SMTP_PASSWORD",
                "from_address": "noreply@example.com",
                "to_addresses": ["admin@example.com"],
                "on_errors": True,
                "on_sync_complete": False,
                "on_quota_warning": True
            },
            "webhook": {
                "enabled": False,
                "url": "https://example.com/webhook",
                "secret_env": "WEBHOOK_SECRET",
                "events": ["error", "quota_warning", "sync_complete"]
            }
        }
    },
    "file_processing": {
        "pipelines": [
            {
                "name": "document_ocr",
                "description": "Extract text from images and PDFs using OCR",
                "file_patterns": ["*.jpg", "*.jpeg", "*.png", "*.pdf"],
                "source_folders": ["xy3_documents", "xy3_images"],
                "output_format": "txt",
                "keep_original": True,
                "move_processed_to": "xy4_archives/processed",
                "enable_parallel_processing": True,
                "max_workers": 4
            },
            {
                "name": "csv_processing",
                "description": "Process CSV files with pandas",
                "file_patterns": ["*.csv"],
                "source_folders": ["xy3_documents"],
                "operations": [
                    {
                        "name": "clean_data",
                        "type": "pandas",
                        "script": "df.dropna(inplace=True)"
                    },
                    {
                        "name": "add_timestamp",
                        "type": "pandas",
                        "script": "df['processed_at'] = pd.Timestamp.now()"
                    }
                ],
                "output_format": "parquet",
                "compression": "gzip"
            }
        ]
    },
    "monitoring": {
        "prometheus": {
            "enabled": True,
            "port": 9091,
            "metrics_path": "/metrics"
        },
        "health_check": {
            "enabled": True,
            "port": 8080,
            "endpoint": "/health"
        },
        "sentry": {
            "enabled": False,
            "dsn_env": "SENTRY_DSN",
            "environment": "production"
        }
    }
}

ENV_TEMPLATE = """# AI Automation Factory Environment Variables
# Google Drive API Credentials
GOOGLE_APPLICATION_CREDENTIALS=\"path/to/credentials.json\"

# Database Configuration
DATABASE_URL=\"sqlite+aiosqlite:///./data/ai_factory.db"

# Logging Configuration
LOG_LEVEL=\"INFO\"
LOG_FILE=\"logs/ai_factory.log\"

# Monitoring
PROMETHEUS_PORT=9091
HEALTH_CHECK_PORT=8080

# Email Notifications (Optional)
SMTP_SERVER=\"smtp.example.com\"
SMTP_PORT=587
SMTP_USERNAME=\"user@example.com\"
SMTP_PASSWORD=\"your_password\"
NOTIFICATION_EMAIL=\"admin@example.com\"
"""

def check_python_version() -> bool:
    """Check if the Python version meets requirements."""
    major, minor = sys.version_info[:2]
    if (major, minor) < REQUIRED_PYTHON:
        print(f"Error: Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}+ is required. You have {major}.{minor}")
        return False
    return True

def create_directories(base_path: Path) -> None:
    """Create required directories."""
    for directory in DIRECTORIES:
        path = base_path / directory
        path.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {path}")

def create_config_files(base_path: Path) -> None:
    """Create configuration files if they don't exist."""
    # Create drive_config.json
    config_path = base_path / "config" / "drive_config.json"
    if not config_path.exists():
        with open(config_path, 'w') as f:
            json.dump(CONFIG_TEMPLATE, f, indent=2)
        print(f"Created configuration file: {config_path}")
    
    # Create .env file
    env_path = base_path / ".env"
    if not env_path.exists():
        with open(env_path, 'w') as f:
            f.write(ENV_TEMPLATE)
        print(f"Created environment file: {env_path}")
    
    # Create .gitignore
    gitignore_path = base_path / ".gitignore"
    if not gitignore_path.exists():
        gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Environment variables
.env

# Credentials
*.json
*.pem
*.key

# Logs
logs/
*.log

# IDE
.idea/
.vscode/
*.swp
*.swo

# System
.DS_Store
Thumbs.db

# Local development
.venv/
venv/
ENV/

# Data
data/
!data/.gitkeep
"""
        with open(gitignore_path, 'w') as f:
            f.write(gitignore_content)
        print(f"Created .gitignore file: {gitignore_path}")

def install_packages() -> bool:
    """Install required Python packages."""
    print("\nInstalling required packages...")
    
    # Prepare pip command
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]
    
    # Add package requirements
    cmd.extend(REQUIRED_PACKAGES)
    
    try:
        subprocess.check_call(cmd)
        print("\nSuccessfully installed all required packages!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\nFailed to install packages: {e}")
        return False

def setup_windows_service() -> None:
    """Set up the Windows service."""
    if platform.system() != 'Windows':
        print("Windows service setup is only available on Windows.")
        return
    
    print("\nSetting up Windows service...")
    
    try:
        # Install the service
        service_script = Path(__file__).parent / "workflows" / "service_manager.py"
        subprocess.check_call([
            sys.executable, str(service_script), "install"
        ])
        
        print("\nWindows service installed successfully!")
        print("You can start the service with: python service_manager.py start")
        
    except subprocess.CalledProcessError as e:
        print(f"\nFailed to install Windows service: {e}")
        print("You may need to run this script as administrator.")

def print_success_message() -> None:
    """Print a success message with next steps."""
    print("\n" + "=" * 80)
    print("AI Automation Factory Setup Complete!")
    print("=" * 80)
    print("\nNEXT STEPS:")
    print("1. Configure your Google Drive API credentials:")
    print("   - Go to https://console.cloud.google.com/")
    print("   - Create a new project")
    print("   - Enable the Google Drive API")
    print("   - Create OAuth 2.0 credentials")
    print("   - Download the credentials and save them to config/credentials_xy3.json and config/credentials_xy4.json")
    print("\n2. Edit the configuration files:")
    print("   - config/drive_config.json: Update folder IDs and other settings")
    print("   - .env: Update environment variables")
    print("\n3. Run the service:")
    print("   python -m workflows.service_manager start")
    print("\nFor more information, see the README.md file.")
    print("=" * 80)

def main():
    """Main setup function."""
    print("\n" + "=" * 80)
    print("AI Automation Factory Setup")
    print("=" * 80)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Get the base directory
    base_path = Path(__file__).parent.absolute()
    
    try:
        # Create directories
        print("\nCreating directories...")
        create_directories(base_path)
        
        # Create config files
        print("\nCreating configuration files...")
        create_config_files(base_path)
        
        # Install packages
        if not install_packages():
            print("\nWarning: Some packages failed to install. You may need to install them manually.")
        
        # Set up Windows service if on Windows
        if platform.system() == 'Windows':
            setup_windows_service()
        
        # Print success message
        print_success_message()
        
    except Exception as e:
        print(f"\nError during setup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
