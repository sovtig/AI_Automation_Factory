import os
import shutil
import zipfile
import hashlib
from pathlib import Path
from typing import Optional, Union, List, Dict, Any, AsyncGenerator
from datetime import datetime, timezone
from loguru import logger
import asyncio
import aiofiles
import aiofiles.os
from dataclasses import dataclass
from enum import Enum

class FileType(Enum):
    """Supported file types."""
    TEXT = "text"
    JSON = "json"
    CSV = "csv"
    BINARY = "binary"
    ARCHIVE = "archive"

@dataclass
class FileMetadata:
    """File metadata container."""
    path: Path
    size: int
    modified: datetime
    file_type: FileType

class FileManager:
    """Manages file operations with support for compression and Google Drive integration."""
    
    def __init__(self, base_dir: str = "./data"):
        """
        Initialize the FileManager with base directories.
        
        Args:
            base_dir: Base directory for all file operations
        """
        self.base_dir = Path(base_dir).resolve()
        self.working_dir = self.base_dir / "working"
        self.output_dir = self.base_dir / "output"
        self.temp_dir = self.base_dir / "temp"
        
        # Create directories if they don't exist
        for directory in [self.base_dir, self.working_dir, self.output_dir, self.temp_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            
        self.logger = logger.bind(component="FileManager")
        
    async def create_file(self, content: Union[str, bytes], filename: str, subdir: str = "") -> Path:
        """
        Create a new file with the given content.
        
        Args:
            content: Content to write to the file
            filename: Name of the file to create
            subdir: Optional subdirectory within the working directory
            
        Returns:
            Path to the created file
        """
        target_dir = self.working_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = target_dir / filename
        
        try:
            mode = 'wb' if isinstance(content, bytes) else 'w'
            encoding = None if isinstance(content, bytes) else 'utf-8'
            async with aiofiles.open(file_path, mode, encoding=encoding) as f:
                await f.write(content)
            self.logger.info(f"Created file: {file_path}")
            return file_path
        except (IOError, PermissionError) as e:
            self.logger.error(f"Error creating file {file_path}: {str(e)}")
            raise
            
    async def read_file(self, filepath: Union[str, Path], binary: bool = False) -> Union[str, bytes]:
        """
        Read content from a file.
        
        Args:
            filepath: Path to the file to read
            binary: Whether to read the file in binary mode
            
        Returns:
            File content as string or bytes
        """
        filepath = Path(filepath)
        if not filepath.is_absolute():
            filepath = self.working_dir / filepath
            
        mode = 'rb' if binary else 'r'
        encoding = None if binary else 'utf-8'
        
        try:
            async with aiofiles.open(filepath, mode=mode, encoding=encoding) as f:
                content = await f.read()
            self.logger.debug(f"Read {len(content)} bytes from {filepath}")
            return content
        except (IOError, PermissionError) as e:
            self.logger.error(f"Error reading file {filepath}: {str(e)}")
            raise
            
    async def create_archive(self, source_paths: List[Union[str, Path]], 
                           archive_name: str, format: str = 'zip') -> Path:
        """
        Create an archive (ZIP) from the given files or directories.
        
        Args:
            source_paths: List of files or directories to include in the archive
            archive_name: Name of the output archive (without extension)
            format: Archive format ('zip', 'tar', 'gztar', 'bztar', 'xztar')
            
        Returns:
            Path to the created archive
        """
        if not source_paths:
            raise ValueError("No source paths provided")
            
        # Resolve all source paths
        resolved_paths = []
        for path in source_paths:
            path = Path(path)
            if not path.is_absolute():
                path = self.working_dir / path
            if not path.exists():
                raise FileNotFoundError(f"Source path not found: {path}")
            resolved_paths.append(path)
            
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Add extension if not present
        if not archive_name.endswith(f".{format}"):
            archive_name = f"{archive_name}.{format}"
            
        archive_path = self.output_dir / archive_name
        
        def _create_archive_sync():
            # This function contains blocking I/O and should be run in a separate thread
            if archive_path.exists():
                archive_path.unlink()

            if format == 'zip':
                with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for path in resolved_paths:
                        if path.is_file():
                            zipf.write(path, arcname=path.name)
                        elif path.is_dir():
                            for file in path.rglob('*'):
                                if file.is_file():
                                    arcname = file.relative_to(path.parent)
                                    zipf.write(file, arcname=arcname)
                return str(archive_path)
            else:
                base_name = str(archive_path.with_suffix(''))
                root_dir = str(resolved_paths[0].parent) if len(resolved_paths) == 1 and resolved_paths[0].is_dir() else None
                base_dir = str(resolved_paths[0].name) if root_dir else None
                return shutil.make_archive(base_name, format, root_dir, base_dir)

        try:
            result_path_str = await asyncio.to_thread(_create_archive_sync)
            result_path = Path(result_path_str)
            self.logger.info(f"Created archive: {result_path}")
            return result_path
        except (IOError, PermissionError, zipfile.BadZipFile) as e:
            self.logger.error(f"Error creating archive {archive_name}: {str(e)}")
            raise
            
    async def cleanup(self, older_than_days: int = 7) -> Dict[str, int]:
        """
        Clean up old files from the working and temp directories.
        
        Args:
            older_than_days: Delete files older than this many days
            
        Returns:
            Dictionary with cleanup statistics
        """
        cutoff_time = datetime.now(timezone.utc).timestamp() - (older_than_days * 24 * 60 * 60)
        stats = {'working_dir_deleted': 0, 'temp_dir_deleted': 0, 'errors': 0}

        async def _clean_directory_async(directory: Path) -> int:
            deleted_count = 0
            error_count = 0
            for item in directory.rglob('*'):
                try:
                    if await aiofiles.os.path.isfile(item) and (await aiofiles.os.stat(item)).st_mtime < cutoff_time:
                        await aiofiles.os.remove(item)
                        deleted_count += 1
                    elif await aiofiles.os.path.isdir(item) and not [i async for i in aiofiles.os.scandir(item)]:
                        await aiofiles.os.rmdir(item)
                except (IOError, PermissionError) as e:
                    self.logger.error(f"Error cleaning up {item}: {str(e)}")
                    error_count += 1
            return deleted_count, error_count

        try:
            deleted_working, errors_working = await _clean_directory_async(self.working_dir)
            stats['working_dir_deleted'] = deleted_working
            stats['errors'] += errors_working

            deleted_temp, errors_temp = await _clean_directory_async(self.temp_dir)
            stats['temp_dir_deleted'] = deleted_temp
            stats['errors'] += errors_temp

            self.logger.info(f"Cleanup completed. Deleted {stats['working_dir_deleted']} files from working dir, "
                             f"{stats['temp_dir_deleted']} files from temp dir. "
                             f"{stats['errors']} errors occurred.")
            return stats
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during cleanup: {str(e)}")
            stats['errors'] += 1
            return stats
            
    async def get_file_info(self, filepath: Union[str, Path]) -> Dict[str, Any]:
        """
        Get information about a file.
        
        Args:
            filepath: Path to the file
            
        Returns:
            Dictionary with file information
        """
        filepath = Path(filepath)
        if not filepath.is_absolute():
            filepath = self.working_dir / filepath
            
        try:
            stat = await aiofiles.os.stat(filepath)
            return {
                'path': str(filepath),
                'name': filepath.name,
                'size': stat.st_size,
                'created': stat.st_ctime,
                'modified': stat.st_mtime,
                'is_file': await aiofiles.os.path.isfile(filepath),
                'is_dir': await aiofiles.os.path.isdir(filepath),
                'exists': await aiofiles.os.path.exists(filepath)
            }
        except (IOError, PermissionError) as e:
            self.logger.error(f"Error getting info for {filepath}: {str(e)}")
            raise

    async def list_directory(self, directory: Union[str, Path] = "", 
                           recursive: bool = False) -> List[Dict[str, Any]]:
        """
        List contents of a directory.
        
        Args:
            directory: Directory to list (relative to working_dir or absolute)
            recursive: Whether to list recursively
            
        Returns:
            List of dictionaries with file information
        """
        directory = Path(directory)
        if not directory.is_absolute():
            directory = self.working_dir / directory
            
        if not await aiofiles.os.path.isdir(directory):
            raise NotADirectoryError(f"Directory not found: {directory}")

        items = []

        async def _scan(path: Path):
            async for item in aiofiles.os.scandir(path):
                try:
                    stat = await aiofiles.os.stat(item.path)
                    items.append({
                        'name': item.name,
                        'path': str(Path(item.path).relative_to(directory)),
                        'size': stat.st_size,
                        'modified': stat.st_mtime,
                        'is_file': item.is_file(),
                        'is_dir': item.is_dir()
                    })
                    if recursive and item.is_dir():
                        await _scan(Path(item.path))
                except (IOError, PermissionError) as e:
                    self.logger.warning(f"Error processing {item.path}: {str(e)}")

        await _scan(directory)
        return items

    async def close(self):
        """Clean up resources. No-op for this implementation."""
        pass
