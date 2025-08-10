#!/usr/bin/env python3
"""
Google Drive Command Line Interface

A command-line tool for interacting with Google Drive accounts.
"""
import asyncio
import json
import typer
from pathlib import Path
from typing import List, Optional
from loguru import logger
from datetime import datetime

# Add parent directory to path for imports
import sys
sys.path.append(str(Path(__file__).parent.parent))

from workflows.drive_integration import DriveManager
from workflows.drive_sync import DriveSync

app = typer.Typer(help="Google Drive CLI Tool")

# Global drive manager instance
drive_manager = DriveManager("./config")

@app.command()
def list_accounts():
    """List all configured Google Drive accounts."""
    try:
        config_path = Path("./config/drive_config.json")
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        typer.echo("\nConfigured Google Drive Accounts:")
        typer.echo("-" * 50)
        
        for account in config.get('accounts', []):
            typer.echo(f"Name: {account['name']}")
            typer.echo(f"Description: {account.get('description', 'No description')}")
            typer.echo(f"Credentials: {account['credentials_file']}")
            typer.echo("-" * 50)
            
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        raise typer.Exit(1)

@app.command()
async def auth(account_name: str):
    """Authenticate with Google Drive."""
    try:
        success = await drive_manager.authenticate(account_name)
        if success:
            typer.echo(f"Successfully authenticated account: {account_name}")
        else:
            typer.echo(f"Failed to authenticate account: {account_name}", err=True)
            raise typer.Exit(1)
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise typer.Exit(1)

@app.command()
async def upload(
    file_path: str,
    folder_id: str = typer.Option("root", "--folder", "-f", help="Google Drive folder ID"),
    account_name: Optional[str] = None
):
    """Upload a file to Google Drive."""
    try:
        result = await drive_manager.upload_file(file_path, folder_id, account_name)
        if result:
            typer.echo(f"Uploaded {file_path} to Google Drive")
            typer.echo(f"File ID: {result.get('id')}")
            typer.echo(f"View URL: {result.get('webViewLink')}")
        else:
            typer.echo("Upload failed", err=True)
            raise typer.Exit(1)
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise typer.Exit(1)

@app.command()
async def download(
    file_id: str,
    output_path: str = "./downloads",
    account_name: Optional[str] = None
):
    """Download a file from Google Drive."""
    try:
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        
        success = await drive_manager.download_file(file_id, output_path, account_name)
        if success:
            typer.echo(f"Downloaded file to {output_path}")
        else:
            typer.echo("Download failed", err=True)
            raise typer.Exit(1)
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise typer.Exit(1)

@app.command()
async def list_files(
    query: str = "",
    account_name: Optional[str] = None,
    limit: int = 10,
    show_all: bool = typer.Option(False, "--all", help="Show all files")
):
    """List files in Google Drive."""
    try:
        if not show_all and not query:
            query = "mimeType != 'application/vnd.google-apps.folder'"
        
        files = await drive_manager.list_files(query, account_name)
        
        if not files:
            typer.echo("No files found")
            return
        
        typer.echo(f"\nFound {len(files)} files:")
        typer.echo("-" * 100)
        
        for i, file in enumerate(files[:limit] if not show_all else files, 1):
            modified = file.get('modifiedTime', 'N/A')
            if modified != 'N/A':
                modified = datetime.strptime(
                    modified, '%Y-%m-%dT%H:%M:%S.%fZ'
                ).strftime('%Y-%m-%d %H:%M')
            
            typer.echo(
                f"{i}. {file['name']} ({file.get('mimeType', 'N/A')})\n"
                f"   ID: {file['id']}\n"
                f"   Size: {self._format_size(file.get('size', 0))} | "
                f"Modified: {modified}"
            )
            typer.echo("-" * 100)
            
        if not show_all and len(files) > limit:
            typer.echo(f"\nShowing {limit} of {len(files)} files. Use --all to show all.")
            
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise typer.Exit(1)

@app.command()
async def sync(
    start: bool = typer.Option(False, help="Start the sync service"),
    stop: bool = typer.Option(False, help="Stop the sync service"),
    status: bool = typer.Option(False, help="Show sync status")
):
    """Manage Google Drive sync service."""
    sync_service = DriveSync()
    
    if start:
        typer.echo("Starting sync service...")
        await sync_service.start()
    elif stop:
        typer.echo("Stopping sync service...")
        await sync_service.stop()
    elif status:
        await sync_service.load_config()
        typer.echo("\nSync Status:")
        typer.echo("-" * 50)
        
        for task_id, task in sync_service.sync_tasks.items():
            last_sync = (
                datetime.fromtimestamp(task.last_sync).strftime('%Y-%m-%d %H:%M:%S')
                if task.last_sync else 'Never'
            )
            
            typer.echo(f"Task: {task_id}")
            typer.echo(f"Local Path: {task.local_path}")
            typer.echo(f"Status: {'Running' if task.is_running else 'Idle'}")
            typer.echo(f"Last Sync: {last_sync}")
            typer.echo("-" * 50)
    else:
        typer.echo("Please specify an action: --start, --stop, or --status")
        raise typer.Exit(1)

def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if not size_bytes:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"

if __name__ == "__main__":
    app()
