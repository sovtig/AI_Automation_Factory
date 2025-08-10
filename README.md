# AI Automation Factory

A powerful, scalable framework for AI-powered task automation with Google Drive integration, designed to handle complex workflows with reliability and efficiency.

## Features

- **Automated File Management**: Seamless sync between local directories and Google Drive
- **Multi-Account Support**: Manage multiple Google Drive accounts simultaneously
- **Intelligent File Processing**: OCR, document conversion, and data extraction
- **Windows Service**: Run as a background service with automatic startup
- **Real-time Monitoring**: Track operations with Prometheus metrics
- **Task Automation**: Schedule and execute tasks with priority support
- **Extensible Architecture**: Easily add new file processors and integrations
- **Comprehensive Logging**: Detailed logs with rotation and retention
- **Error Recovery**: Built-in retries and failure handling

## 🚀 Quick Start

### Prerequisites

- Windows 10/11 or Linux/macOS
- Python 3.9+
- Google Drive API credentials (for cloud sync)
- Administrator/root access (for service installation)

### Automated Installation (Windows)

1. **Download and Extract** the latest release
2. **Run as Administrator**: Right-click `install_and_run.ps1` and select "Run with PowerShell"
3. **Follow the prompts** to complete the setup
4. **Configure** your Google Drive API credentials in `config/drive_config.json`

### Manual Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/ai-automation-factory.git
   cd ai-automation-factory
   ```

2. **Run the setup script**:
   ```powershell
   # Windows
   .\setup.py
   
   # Linux/macOS
   python3 setup.py
   ```

3. **Configure your settings** in `config/drive_config.json` and `.env`

### Running the Application

#### As a Windows Service (Recommended)
```powershell
# Install the service (requires admin)
python -m workflows.service_manager install

# Start the service
python -m workflows.service_manager start

# Check status
python -m workflows.service_manager status
```

#### Manually
```bash
# Start the sync service
python -m workflows.drive_sync

# Or use the CLI for manual operations
python -m scripts.drive_cli --help
```

#### Web Interface (Optional)
```bash
uvicorn main:app --reload
# Access at http://localhost:8000/docs
```

## 📂 Project Structure

```
AI_Automation_Factory/
├── config/              # Configuration files
│   └── drive_config.json  # Google Drive and sync settings
├── data/                # Working directories
│   ├── sync/            # Synced folders
│   ├── processed/       # Processed files
│   └── backup/          # Backups
├── logs/               # Log files
├── scripts/            # Utility scripts
│   └── drive_cli.py    # Command-line interface
├── tests/              # Test suite
├── workflows/          # Core components
│   ├── drive_integration.py  # Google Drive API
│   ├── drive_sync.py   # Sync service
│   ├── file_processor.py     # File processing
│   ├── file_watcher.py # Directory monitoring
│   ├── monitoring.py   # Metrics and logging
│   └── service_manager.py    # Windows service
├── install_and_run.ps1 # Windows installer
├── setup.py           # Setup script
└── requirements.txt   # Dependencies
```

## 🔧 Configuration

### Google Drive Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project and enable Google Drive API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download credentials as `config/credentials_xy3.json`
5. Repeat for additional accounts (xy4, etc.)

### drive_config.json
```json
{
  "accounts": [
    {
      "name": "xy_drive_3",
      "credentials_file": "credentials_xy3.json",
      "token_file": "token_xy3.json"
    }
  ],
  "sync_folders": [
    {
      "name": "documents",
      "local_path": "./data/sync/documents",
      "drive_folder_id": "YOUR_FOLDER_ID",
      "account": "xy_drive_3"
    }
  ]
}
```

### Environment Variables (`.env`)
```ini
# Google Drive API
GOOGLE_APPLICATION_CREDENTIALS="config/credentials_xy3.json"

# Database
DATABASE_URL="sqlite+aiosqlite:///./data/ai_factory.db"

# Logging
LOG_LEVEL="INFO"
LOG_FILE="logs/ai_factory.log"

# Monitoring
PROMETHEUS_PORT=9091
HEALTH_CHECK_PORT=8080
```

## 🛠️ Usage Examples

### Using the CLI

```bash
# List available commands
python -m scripts.drive_cli --help

# Authenticate with Google Drive
python -m scripts.drive_cli auth --account xy_drive_3

# List files in a folder
python -m scripts.drive_cli list --account xy_drive_3 --folder-id FOLDER_ID

# Upload a file
python -m scripts.drive_cli upload --account xy_drive_3 --file example.pdf --folder-id FOLDER_ID

# Start sync service
python -m workflows.drive_sync
```

### Monitoring and Logs

- **Metrics**: `http://localhost:9091/metrics`
- **Health Check**: `http://localhost:8080/health`
- **Logs**: Check `logs/` directory for detailed logs

### File Processing Pipeline

1. Add files to a watched directory
2. The system automatically processes them based on file type
3. Processed files are moved to the output directory
4. Results are synced to Google Drive

### Custom Processors

Add custom file processors in `workflows/file_processor.py`:

```python
@register_processor("custom_type")
async def process_custom_file(file_info: FileInfo) -> bool:
    """Process files with custom logic."""
    try:
        # Your processing logic here
        logger.info(f"Processing {file_info.path}")
        return True
    except Exception as e:
        logger.error(f"Error processing {file_info.path}: {e}")
        return False
```

## 🚨 Troubleshooting

### Common Issues

1. **Authentication Errors**:
   - Delete the token file and re-authenticate
   - Check Google Cloud Console for API access

2. **Sync Issues**:
   - Check `logs/sync.log` for errors
   - Verify folder permissions in Google Drive

3. **Service Not Starting**:
   - Run `python -m workflows.service_manager debug` for details
   - Check Windows Event Viewer for service errors

## 🔄 Updates

To update to the latest version:

```bash
git pull
pip install -r requirements.txt
python -m workflows.service_manager restart
```

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

## 📧 Contact

For support or questions, please open an issue on GitHub.

## 🙏 Acknowledgments

- Google Drive API Team
- Python Community
- Open Source Contributors
