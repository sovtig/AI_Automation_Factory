"""
Google Drive Sync Service for AI Automation Factory

Handles automatic synchronization between local directories and Google Drive.
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from loguru import logger
import hashlib
import aiofiles
import aiofiles.os
from datetime import datetime, timedelta

from .drive_integration import DriveManager

@dataclass
class SyncConfig:
    """Configuration for a sync task."""
    local_path: Path
    drive_folder_id: str
    account_name: str
    sync_interval: int = 3600  # seconds
    last_sync: Optional[float] = None
    is_running: bool = False
    
    def __post_init__(self):
        self.local_path = Path(self.local_path).resolve()

class DriveSync:
    """Manages synchronization between local files and Google Drive."""
    
    def __init__(self, config_path: Union[str, Path] = "./config/drive_config.json"):
        """Initialize with path to configuration file."""
        self.config_path = Path(config_path)
        self.drive_manager = DriveManager(self.config_path.parent)
        self.sync_tasks: Dict[str, SyncConfig] = {}
        self._sync_interval = 60  # Check for sync every minute
        self._running = False
        logger.info(f"Initialized DriveSync with config: {self.config_path}")
    
    async def load_config(self) -> bool:
        """Load synchronization configuration from file."""
        try:
            async with aiofiles.open(self.config_path, 'r') as f:
                config = json.loads(await f.read())
            
            # Add accounts
            for account in config.get('accounts', []):
                await self.drive_manager.add_account(
                    name=account['name'],
                    credentials_file=account['credentials_file'],
                    token_file=account.get('token_file')
                )
                await self.drive_manager.authenticate(account['name'])
            
            # Set default account
            if 'default_account' in config:
                self.drive_manager.default_account = config['default_account']
            
            # Configure sync tasks
            for sync in config.get('sync_folders', []):
                task_id = f"{sync['account']}:{sync['drive_folder_id']}"
                self.sync_tasks[task_id] = SyncConfig(
                    local_path=sync['local_path'],
                    drive_folder_id=sync['drive_folder_id'],
                    account_name=sync['account'],
                    sync_interval=sync.get('sync_interval', 3600)
                )
            
            logger.info(f"Loaded {len(self.sync_tasks)} sync tasks")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return False
    
    async def start(self):
        """Start the sync service."""
        if not await self.load_config():
            logger.error("Failed to start sync service: invalid configuration")
            return False
        
        self._running = True
        asyncio.create_task(self._sync_loop())
        logger.info("DriveSync service started")
        return True
    
    async def stop(self):
        """Stop the sync service."""
        self._running = False
        logger.info("DriveSync service stopping...")
    
    async def _sync_loop(self):
        """Main sync loop that runs periodically."""
        while self._running:
            try:
                current_time = time.time()
                
                for task_id, task in self.sync_tasks.items():
                    if task.is_running:
                        continue
                        
                    if task.last_sync is None or \
                       (current_time - task.last_sync) >= task.sync_interval:
                        
                        task.is_running = True
                        asyncio.create_task(
                            self.sync_folder(task)
                        )
                
                await asyncio.sleep(self._sync_interval)
                
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                await asyncio.sleep(5)  # Prevent tight loop on errors
    
    async def sync_folder(self, task: SyncConfig) -> bool:
        """Synchronize a single folder."""
        try:
            logger.info(f"Starting sync: {task.local_path} -> {task.drive_folder_id}")
            
            # Ensure local directory exists
            await aiofiles.os.makedirs(task.local_path, exist_ok=True)
            
            # Get local files
            local_files = await self._get_local_files(task.local_path)
            
            # Get remote files
            remote_files = await self.drive_manager.list_files(
                f"'{task.drive_folder_id}' in parents",
                account_name=task.account_name
            )
            
            # Upload new or modified files
            for local_file in local_files:
                remote_file = next(
                    (f for f in remote_files if f['name'] == local_file['name']), 
                    None
                )
                
                if not remote_file or self._is_file_modified(local_file, remote_file):
                    await self.drive_manager.upload_file(
                        local_file['path'],
                        task.drive_folder_id,
                        task.account_name
                    )
            
            # Download missing files
            for remote_file in remote_files:
                local_file = next(
                    (f for f in local_files if f['name'] == remote_file['name']),
                    None
                )
                
                if not local_file:
                    local_path = task.local_path / remote_file['name']
                    await self.drive_manager.download_file(
                        remote_file['id'],
                        local_path,
                        task.account_name
                    )
            
            task.last_sync = time.time()
            logger.info(f"Completed sync: {task.local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Sync failed for {task.local_path}: {e}")
            return False
            
        finally:
            task.is_running = False
    
    async def _get_local_files(self, path: Path) -> List[Dict]:
        """Get list of files in local directory with metadata."""
        files = []
        
        try:
            async for entry in aiofiles.os.scandir(path):
                if entry.is_file():
                    stat = await aiofiles.os.stat(entry.path)
                    files.append({
                        'name': entry.name,
                        'path': Path(entry.path),
                        'size': stat.st_size,
                        'modified': stat.st_mtime,
                        'checksum': await self._calculate_checksum(entry.path)
                    })
        except Exception as e:
            logger.error(f"Error scanning local directory {path}: {e}")
            
        return files
    
    async def _calculate_checksum(self, file_path: Union[str, Path], 
                                chunk_size: int = 8192) -> str:
        """Calculate MD5 checksum of a file."""
        hash_md5 = hashlib.md5()
        
        try:
            async with aiofiles.open(file_path, "rb") as f:
                while chunk := await f.read(chunk_size):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating checksum for {file_path}: {e}")
            return ""
    
    def _is_file_modified(self, local_file: Dict, remote_file: Dict) -> bool:
        """Check if a file has been modified based on size and modification time."""
        remote_modified = datetime.strptime(
            remote_file.get('modifiedTime', '1970-01-01T00:00:00.000Z'),
            '%Y-%m-%dT%H:%M:%S.%fZ'
        ).timestamp()
        
        return (
            local_file['size'] != int(remote_file.get('size', 0)) or
            local_file['modified'] > remote_modified
        )

# Example usage
async def example():
    # Initialize and start the sync service
    sync_service = DriveSync()
    await sync_service.start()
    
    try:
        # Keep the service running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await sync_service.stop()
        print("\nSync service stopped")

if __name__ == "__main__":
    asyncio.run(example())
