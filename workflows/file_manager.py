"""
Automated File Management System for AI Automation Factory

Handles file operations asynchronously with support for various file types
and automated processing pipelines.
"""

import os
import shutil
import zipfile
import hashlib
import tempfile
from pathlib import Path
from typing import Optional, Union, List, Dict, Any, AsyncGenerator
from datetime import datetime
from loguru import logger
import asyncio
import aiofiles
import aiofiles.os
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor  # <-- FIXED: Added this import

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
            
        self.executor = ThreadPoolExecutor(max_workers=4)  # <-- This will now work!
        self.logger = logger.bind(component="FileManager")
        
    def _resolve_path(self, path: Union[str, Path]) -> Path:
        """Resolve path relative to base directory."""
        path = Path(path)
        return (self.base_dir / path).resolve() if not path.is_absolute() else path

    async def ensure_dir(self, path: Union[str, Path]) -> Path:
        """Ensure directory exists."""
        path = self._resolve_path(path)
        await aiofiles.os.makedirs(path, exist_ok=True)
        return path

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
        
        def _read_file():
            with open(filepath, mode, encoding=encoding) as f:
                return f.read()
                
        try:
            loop = asyncio.get_running_loop()
            content = await loop.run_in_executor(self.executor, _read_file)
            self.logger.debug(f"Read {len(content)} bytes from {filepath}")
            return content
        except Exception as e:
            self.logger.error(f"Error reading file {filepath}: {str(e)}")
            raise

    async def write_file(self, path: Union[str, Path], content: Union[str, bytes], 
                        binary: bool = False) -> Path:
        """Write content to file."""
        path = self._resolve_path(path)
        await self.ensure_dir(path.parent)
        mode = 'wb' if binary or isinstance(content, bytes) else 'w'
        async with aiofiles.open(path, mode) as f:
            await f.write(content)
        return path

    async def create_file(self, content: str, filename: str, subdir: str = "") -> Path:
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
        
        def _write_file():
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return file_path
            
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(self.executor, _write_file)
            self.logger.info(f"Created file: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error creating file {file_path}: {str(e)}")
            raise

    async def process_files(self, input_dir: str, pattern: str = '*', 
                          processor: callable = None) -> List[Dict]:
        """Process files matching pattern with given processor."""
        input_dir = self._resolve_path(input_dir)
        results = []
        
        for file_path in input_dir.glob(pattern):
            if not await aiofiles.os.path.isfile(file_path):
                continue
                
            try:
                content = await self.read_file(file_path)
                if processor:
                    result = await processor(content) if asyncio.iscoroutinefunction(processor) \
                             else await asyncio.get_running_loop().run_in_executor(None, processor, content)
                    results.append({"file": str(file_path), "result": result})
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                results.append({"file": str(file_path), "error": str(e)})
                
        return results
            
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
        
        def _create_archive():
            # Remove existing archive if it exists
            if archive_path.exists():
                archive_path.unlink()
                
            # Create the archive
            if format == 'zip':
                with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for path in resolved_paths:
                        if path.is_file():
                            # Add file at the root of the archive
                            zipf.write(path, arcname=path.name)
                        elif path.is_dir():
                            # Add directory and all its contents
                            for file in path.rglob('*'):
                                if file.is_file():
                                    # Preserve directory structure relative to the source directory
                                    arcname = file.relative_to(path.parent)
                                    zipf.write(file, arcname=arcname)
            else:
                # For non-zip formats, use shutil.make_archive
                base_name = str(archive_path.with_suffix(''))
                root_dir = None
                
                # If all sources are in the same directory, use it as root
                if len(resolved_paths) == 1 and resolved_paths[0].is_dir():
                    root_dir = str(resolved_paths[0].parent)
                    base_dir = str(resolved_paths[0].name)
                    return shutil.make_archive(base_name, format, root_dir, base_dir)
                else:
                    # For multiple files or files from different directories, create a temp dir
                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_path = Path(temp_dir)
                        for src in resolved_paths:
                            dest = temp_path / src.name
                            if src.is_file():
                                shutil.copy2(src, dest)
                            elif src.is_dir():
                                shutil.copytree(src, dest, dirs_exist_ok=True)
                        return shutil.make_archive(base_name, format, temp_dir)
            
            return archive_path
            
        try:
            loop = asyncio.get_running_loop()
            result_path = await loop.run_in_executor(self.executor, _create_archive)
            self.logger.info(f"Created archive: {result_path}")
            return Path(result_path)
        except Exception as e:
            self.logger.error(f"Error creating archive: {str(e)}")
            raise
            
    async def cleanup(self, older_than_days: int = 7) -> Dict[str, int]:
        """
        Clean up old files from the working and temp directories.
        
        Args:
            older_than_days: Delete files older than this many days
            
        Returns:
            Dictionary with cleanup statistics
        """
        cutoff_time = datetime.now().timestamp() - (older_than_days * 24 * 60 * 60)
        stats = {
            'working_dir_deleted': 0,
            'temp_dir_deleted': 0,
            'errors': 0
        }
        
        def _clean_directory(directory: Path) -> int:
            deleted = 0
            for item in directory.rglob('*'):
                try:
                    if item.is_file() and item.stat().st_mtime < cutoff_time:
                        item.unlink()
                        deleted += 1
                    elif item.is_dir() and not any(item.iterdir()):
                        # Remove empty directories
                        item.rmdir()
                except Exception as e:
                    self.logger.error(f"Error cleaning up {item}: {str(e)}")
                    stats['errors'] += 1
            return deleted
            
        try:
            loop = asyncio.get_running_loop()
            
            # Clean working directory (preserve directory structure)
            stats['working_dir_deleted'] = await loop.run_in_executor(
                self.executor, _clean_directory, self.working_dir
            )
            
            # Clean temp directory (can be more aggressive)
            stats['temp_dir_deleted'] = await loop.run_in_executor(
                self.executor, _clean_directory, self.temp_dir
            )
            
            self.logger.info(
                f"Cleanup completed. Deleted {stats['working_dir_deleted']} files from working directory, "
                f"{stats['temp_dir_deleted']} files from temp directory"
            )
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
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
            stat = filepath.stat()
            return {
                'path': str(filepath),
                'name': filepath.name,
                'size': stat.st_size,
                'created': stat.st_ctime,
                'modified': stat.st_mtime,
                'is_file': filepath.is_file(),
                'is_dir': filepath.is_dir(),
                'exists': filepath.exists()
            }
        except Exception as e:
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
            
        if not directory.exists() or not directory.is_dir():
            raise NotADirectoryError(f"Directory not found: {directory}")
            
        def _list_dir():
            items = []
            if recursive:
                iterator = directory.rglob('*')
            else:
                iterator = directory.iterdir()
                
            for item in iterator:
                try:
                    stat = item.stat()
                    items.append({
                        'name': item.name,
                        'path': str(item.relative_to(directory)),
                        'size': stat.st_size,
                        'modified': stat.st_mtime,
                        'is_file': item.is_file(),
                        'is_dir': item.is_dir()
                    })
                except Exception as e:
                    self.logger.warning(f"Error processing {item}: {str(e)}")
            return items
            
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self.executor, _list_dir)
        except Exception as e:
            self.logger.error(f"Error listing directory {directory}: {str(e)}")
            raise

    async def close(self):
        """Clean up resources."""
        self.executor.shutdown(wait=True)
