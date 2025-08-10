"""
File Watcher for AI Automation Factory

Watches directories for changes and triggers processing pipelines.
"""
import os
import time
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable, Awaitable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from loguru import logger

from .file_processor import FileProcessor, FileInfo
from .monitoring import monitor, log_file_operation

@dataclass
class WatchConfig:
    """Configuration for watching a directory."""
    path: Path
    account: str
    recursive: bool = True
    patterns: List[str] = field(default_factory=list)
    ignore_patterns: List[str] = field(default_factory=list)
    cooldown: float = 5.0  # seconds
    process_existing: bool = False
    move_processed: Optional[str] = None
    
    def __post_init__(self):
        self.path = Path(self.path).resolve()
        if not self.patterns:
            self.patterns = ['*']

class FileWatcher:
    """Watches directories and processes new or modified files."""
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """Initialize the file watcher with configuration."""
        self.config_path = Path(config_path) if config_path else Path("config/drive_config.json")
        self.watch_configs: List[WatchConfig] = []
        self.observer = Observer()
        self.processor = FileProcessor(self.config_path)
        self._file_events: Dict[Path, float] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._event_handlers: Dict[str, List[Callable[[FileSystemEvent], Awaitable[None]]]] = {
            'created': [],
            'modified': [],
            'deleted': [],
            'moved': []
        }
        
        # Load configuration
        self._load_config()
        
        # Set up event handlers
        self._setup_handlers()
        
        logger.info(f"Initialized FileWatcher with {len(self.watch_configs)} watch configurations")
    
    def _load_config(self) -> None:
        """Load watch configurations from the config file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Load watch configurations
            for watch in config.get('watch_directories', []):
                self.watch_configs.append(WatchConfig(
                    path=watch['path'],
                    account=watch['account'],
                    recursive=watch.get('recursive', True),
                    patterns=watch.get('patterns', ['*']),
                    ignore_patterns=watch.get('ignore_patterns', []),
                    cooldown=watch.get('cooldown', 5.0),
                    process_existing=watch.get('process_existing', False),
                    move_processed=watch.get('move_processed')
                ))
                
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
    
    def _setup_handlers(self) -> None:
        """Set up event handlers for file system events."""
        # Default handler that adds events to the queue
        async def default_handler(event: FileSystemEvent) -> None:
            if event.is_directory:
                return
                
            src_path = Path(event.src_path)
            
            # Check if we should ignore this event
            if self._should_ignore(src_path):
                return
                
            # Check cooldown
            current_time = time.time()
            last_event = self._file_events.get(src_path, 0)
            if current_time - last_event < 1.0:  # 1 second cooldown per file
                return
                
            self._file_events[src_path] = current_time
            
            # Add to processing queue
            await self._event_queue.put((event, current_time))
            
            logger.debug(f"Queued {event.event_type} event for {src_path}")
        
        # Register default handlers
        for event_type in self._event_handlers.keys():
            self._event_handlers[event_type].append(default_handler)
    
    def _should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored based on patterns."""
        path_str = str(path).lower()
        
        # Check against common temporary files
        temp_patterns = ['~$', '.tmp', '.temp', '._', 'Thumbs.db', '.DS_Store']
        if any(p in path_str for p in temp_patterns):
            return True
            
        # Check against configured ignore patterns
        for config in self.watch_configs:
            if path.is_relative_to(config.path):
                for pattern in config.ignore_patterns:
                    if self._matches_pattern(path, pattern):
                        return True
                        
        return False
    
    def _matches_pattern(self, path: Path, pattern: str) -> bool:
        """Check if a path matches a pattern."""
        # Convert pattern to regex
        regex = re.compile(
            pattern
            .replace('.', '\.')
            .replace('*', '.*')
            .replace('?', '.')
            .lower()
        )
        return bool(regex.fullmatch(str(path).lower()))
    
    async def _process_event(self, event: FileSystemEvent, event_time: float) -> None:
        """Process a file system event."""
        try:
            src_path = Path(event.src_path)
            
            # Only process created and modified events for files
            if event.is_directory or event.event_type not in ['created', 'modified']:
                return
            
            # Find matching watch config
            config = self._get_matching_config(src_path)
            if not config:
                return
            
            # Check file patterns
            if not any(self._matches_pattern(src_path.name, p) for p in config.patterns):
                return
            
            # Wait for file to be fully written
            await self._wait_for_file_stable(src_path, config.cooldown)
            
            # Process the file
            file_info = FileInfo(
                path=src_path,
                account=config.account,
                pipeline='file_watcher',
                metadata={
                    'event_type': event.event_type,
                    'event_time': event_time,
                    'watch_path': str(config.path)
                }
            )
            
            logger.info(f"Processing {event.event_type} file: {src_path}")
            success = await self.processor.process_file(src_path, config.account)
            
            if success:
                log_file_operation(config.account, f"processed_{event.event_type}")
                
                # Move processed file if configured
                if config.move_processed and src_path.exists():
                    self._move_processed_file(src_path, config.move_processed)
            else:
                logger.error(f"Failed to process file: {src_path}")
                
        except Exception as e:
            logger.error(f"Error processing event: {e}", exc_info=True)
    
    async def _wait_for_file_stable(self, file_path: Path, timeout: float) -> bool:
        """Wait for a file to stop changing."""
        if not file_path.exists():
            return False
            
        start_time = time.time()
        last_size = -1
        stable_time = 0
        
        while time.time() - start_time < timeout:
            try:
                current_size = file_path.stat().st_size
                
                if current_size == last_size:
                    stable_time += 0.1
                    if stable_time >= 1.0:  # Stable for 1 second
                        return True
                else:
                    stable_time = 0
                    last_size = current_size
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"Error checking file size: {e}")
                await asyncio.sleep(0.5)
        
        return file_path.exists()
    
    def _get_matching_config(self, file_path: Path) -> Optional[WatchConfig]:
        """Get the watch configuration that matches the file path."""
        for config in self.watch_configs:
            try:
                if file_path.is_relative_to(config.path):
                    return config
            except ValueError:
                continue
        return None
    
    def _move_processed_file(self, src_path: Path, dest_dir: str) -> None:
        """Move a processed file to the specified directory."""
        try:
            dest_path = Path(dest_dir) / src_path.name
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Handle naming conflicts
            counter = 1
            while dest_path.exists():
                name = f"{src_path.stem}_{counter}{src_path.suffix}"
                dest_path = dest_path.parent / name
                counter += 1
            
            shutil.move(str(src_path), str(dest_path))
            logger.info(f"Moved processed file to {dest_path}")
            
        except Exception as e:
            logger.error(f"Failed to move processed file: {e}")
    
    async def _process_queue(self) -> None:
        """Process events from the queue."""
        while self._running:
            try:
                # Get the next event with timeout to allow checking self._running
                try:
                    event, event_time = await asyncio.wait_for(
                        self._event_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Process the event
                await self._process_event(event, event_time)
                
            except Exception as e:
                logger.error(f"Error in queue processor: {e}", exc_info=True)
            finally:
                self._event_queue.task_done()
    
    async def start(self) -> None:
        """Start the file watcher."""
        if self._running:
            logger.warning("File watcher is already running")
            return
        
        self._running = True
        
        # Start the observer
        self.observer.start()
        
        # Schedule the queue processor
        self._queue_task = asyncio.create_task(self._process_queue())
        
        # Add watches for each configured directory
        for config in self.watch_configs:
            try:
                # Ensure the directory exists
                config.path.mkdir(parents=True, exist_ok=True)
                
                # Add the watch
                self.observer.schedule(
                    FileWatcherHandler(self._event_handlers),
                    str(config.path),
                    recursive=config.recursive
                )
                
                logger.info(f"Watching directory: {config.path}")
                
                # Process existing files if configured
                if config.process_existing:
                    self._process_existing_files(config)
                
            except Exception as e:
                logger.error(f"Failed to watch directory {config.path}: {e}")
        
        logger.info("File watcher started")
    
    def _process_existing_files(self, config: WatchConfig) -> None:
        """Process existing files in a directory."""
        try:
            logger.info(f"Processing existing files in {config.path}")
            
            # Find all matching files
            files = []
            for pattern in config.patterns:
                files.extend(config.path.rglob(pattern))
            
            # Remove duplicates and filter out directories
            files = list({f for f in files if f.is_file()})
            
            # Process each file
            for file_path in files:
                if not self._should_ignore(file_path):
                    asyncio.create_task(
                        self.processor.process_file(file_path, config.account)
                    )
            
            logger.info(f"Queued {len(files)} existing files for processing")
            
        except Exception as e:
            logger.error(f"Error processing existing files: {e}")
    
    async def stop(self) -> None:
        """Stop the file watcher."""
        if not self._running:
            return
        
        self._running = False
        
        # Stop the observer
        self.observer.stop()
        self.observer.join()
        
        # Cancel the queue processor
        if hasattr(self, '_queue_task'):
            self._queue_task.cancel()
            try:
                await self._queue_task
            except asyncio.CancelledError:
                pass
        
        # Wait for queue to be processed
        await self._event_queue.join()
        
        logger.info("File watcher stopped")
    
    def __enter__(self):
        """Context manager entry."""
        asyncio.get_event_loop().run_until_complete(self.start())
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        asyncio.get_event_loop().run_until_complete(self.stop())

class FileWatcherHandler(FileSystemEventHandler):
    """Handler for file system events."""
    
    def __init__(self, event_handlers: Dict[str, List[Callable]]):
        self.event_handlers = event_handlers
    
    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file created event."""
        if not event.is_directory:
            asyncio.create_task(self._dispatch_event('created', event))
    
    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modified event."""
        if not event.is_directory:
            asyncio.create_task(self._dispatch_event('modified', event))
    
    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deleted event."""
        if not event.is_directory:
            asyncio.create_task(self._dispatch_event('deleted', event))
    
    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file moved/renamed event."""
        if not event.is_directory:
            asyncio.create_task(self._dispatch_event('moved', event))
    
    async def _dispatch_event(self, event_type: str, event: FileSystemEvent) -> None:
        """Dispatch event to all registered handlers."""
        for handler in self.event_handlers.get(event_type, []):
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Error in {event_type} handler: {e}", exc_info=True)

# Example usage
async def example():
    # Create and start the file watcher
    watcher = FileWatcher()
    
    try:
        # Start watching
        await watcher.start()
        
        # Keep the script running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Stopping file watcher...")
    finally:
        await watcher.stop()

if __name__ == "__main__":
    import asyncio
    
    # Configure logging
    logger.add(
        "logs/file_watcher.log",
        rotation="10 MB",
        retention="7 days",
        level="INFO"
    )
    
    # Run the example
    asyncio.run(example())
