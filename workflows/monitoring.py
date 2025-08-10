"""
Monitoring and Logging Module for AI Automation Factory

Handles logging, metrics, and monitoring integration.
"""
import os
import json
import time
import socket
import platform
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

import psutil
from loguru import logger
from prometheus_client import start_http_server, Gauge, Counter, Histogram, Summary

# Prometheus Metrics
SYNC_OPS_TOTAL = Counter(
    'drive_sync_operations_total',
    'Total number of sync operations',
    ['account', 'status']
)

SYNC_DURATION = Histogram(
    'drive_sync_duration_seconds',
    'Time spent processing sync operations',
    ['account']
)

FILES_PROCESSED = Counter(
    'drive_files_processed_total',
    'Total number of files processed',
    ['account', 'operation']
)

STORAGE_USAGE = Gauge(
    'drive_storage_usage_bytes',
    'Storage usage in bytes',
    ['account', 'type']
)

SERVICE_UPTIME = Gauge(
    'service_uptime_seconds',
    'Service uptime in seconds'
)

class Monitoring:
    """Handles monitoring and logging for the AI Automation Factory."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize monitoring with configuration."""
        self.config = config or {}
        self.start_time = time.time()
        self.metrics_port = self.config.get('prometheus', {}).get('port', 9091)
        self.health_port = self.config.get('health_check', {}).get('port', 8080)
        self.executor = ThreadPoolExecutor(max_workers=5)
        self._setup_logging()
        self._setup_metrics()
    
    def _setup_logging(self):
        """Configure logging with rotation and formatting."""
        log_config = self.config.get('logging', {})
        log_level = log_config.get('level', 'INFO')
        log_dir = Path(log_config.get('directory', 'logs'))
        log_dir.mkdir(exist_ok=True)
        
        # Remove default logger
        logger.remove()
        
        # Add file logger
        logger.add(
            log_dir / "ai_factory.log",
            rotation=log_config.get('rotation', '10 MB'),
            retention=log_config.get('retention', '7 days'),
            compression=log_config.get('compression', 'zip'),
            level=log_level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
            backtrace=True,
            diagnose=True
        )
        
        # Add console logger if in debug mode
        if os.getenv('DEBUG', '').lower() in ('1', 'true', 't'):
            logger.add(
                sys.stderr,
                level='DEBUG',
                format=(
                    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                    "<level>{level: <8}</level> | "
                    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                    "<level>{message}</level>"
                )
            )
    
    def _setup_metrics(self):
        """Initialize Prometheus metrics and start HTTP server."""
        try:
            # Start Prometheus metrics server
            start_http_server(self.metrics_port)
            logger.info(f"Started metrics server on port {self.metrics_port}")
            
            # Start health check server in background
            self.executor.submit(self._start_health_server)
            
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")
    
    def _start_health_server(self):
        """Start a simple HTTP server for health checks."""
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import json
        
        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/health':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'status': 'healthy',
                        'timestamp': datetime.utcnow().isoformat(),
                        'service': 'ai_factory_drive_sync',
                        'version': '1.0.0',
                        'system': {
                            'hostname': socket.gethostname(),
                            'platform': platform.platform(),
                            'python': platform.python_version()
                        }
                    }).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
        
        server = HTTPServer(('0.0.0.0', self.health_port), HealthHandler)
        logger.info(f"Started health check server on port {self.health_port}")
        server.serve_forever()
    
    def update_metrics(self):
        """Update all metrics."""
        try:
            # Update service uptime
            SERVICE_UPTIME.set(time.time() - self.start_time)
            
            # Update system metrics
            self._update_system_metrics()
            
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
    
    def _update_system_metrics(self):
        """Update system-level metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Update Prometheus metrics
            STORAGE_USAGE.labels(type='memory').set(memory.used)
            STORAGE_USAGE.labels(type='disk').set(disk.used)
            
            # Log system stats periodically
            if int(time.time()) % 300 == 0:  # Every 5 minutes
                logger.info(
                    f"System stats - CPU: {cpu_percent}% | "
                    f"Memory: {memory.percent}% | "
                    f"Disk: {disk.percent}%"
                )
                
        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")
    
    def track_sync_operation(self, account: str):
        """Decorator to track sync operations with metrics."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                status = 'success'
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    status = 'error'
                    logger.error(f"Sync operation failed: {e}")
                    raise
                finally:
                    duration = time.time() - start_time
                    SYNC_OPS_TOTAL.labels(account=account, status=status).inc()
                    SYNC_DURATION.labels(account=account).observe(duration)
                    
                    if status == 'success':
                        logger.info(
                            f"Sync completed for {account} in {duration:.2f}s"
                        )
            
            return wrapper
        return decorator
    
    def track_file_operation(self, account: str, operation: str):
        """Track file operations with metrics."""
        FILES_PROCESSED.labels(account=account, operation=operation).inc()
    
    def log_drive_quota(self, account: str, used: int, total: int):
        """Log and track drive quota usage."""
        if total > 0:
            percent_used = (used / total) * 100
            STORAGE_USAGE.labels(account=account, type='drive').set(used)
            
            if percent_used > 90:
                logger.warning(
                    f"Drive quota warning for {account}: "
                    f"{percent_used:.1f}% used ({used}/{total} bytes)"
                )
    
    def log_error(self, message: str, exc_info=None, extra: Optional[Dict] = None):
        """Log an error with optional exception info and extra context."""
        context = {
            'timestamp': datetime.utcnow().isoformat(),
            'hostname': socket.gethostname(),
            'service': 'ai_factory_drive_sync',
            'level': 'ERROR'
        }
        
        if extra:
            context.update(extra)
        
        logger.error(
            message,
            exc_info=exc_info,
            extra=context
        )
    
    def log_metrics(self):
        """Log current metrics for debugging and monitoring."""
        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'uptime_seconds': time.time() - self.start_time,
            'cpu_percent': psutil.cpu_percent(),
            'memory': dict(psutil.virtual_memory()._asdict()),
            'disk': dict(psutil.disk_usage('/')._asdict()),
            'metrics': {
                'sync_operations': {
                    'total': sum(
                        metric._value.get() 
                        for metric in SYNC_OPS_TOTAL._metrics.values()
                    ),
                    'by_status': {
                        status: metric._value.get()
                        for (account, status), metric in SYNC_OPS_TOTAL._metrics.items()
                    }
                },
                'files_processed': {
                    'total': sum(
                        metric._value.get() 
                        for metric in FILES_PROCESSED._metrics.values()
                    ),
                    'by_operation': {
                        op: metric._value.get()
                        for (_, op), metric in FILES_PROCESSED._metrics.items()
                    }
                }
            }
        }
        
        logger.debug("Current metrics:" + json.dumps(metrics, indent=2, default=str))
        return metrics

# Global monitoring instance
monitor = Monitoring()

def monitor_sync(account: str):
    """Decorator to monitor sync operations."""
    return monitor.track_sync_operation(account)

def log_file_operation(account: str, operation: str):
    """Log a file operation."""
    return monitor.track_file_operation(account, operation)

def log_error(message: str, exc_info=None, **extra):
    """Log an error with context."""
    monitor.log_error(message, exc_info, extra)

if __name__ == "__main__":
    # Example usage
    import asyncio
    
    async def example():
        # Start monitoring
        monitor = Monitoring({
            'prometheus': {'port': 9091},
            'health_check': {'port': 8080},
            'logging': {
                'level': 'DEBUG',
                'directory': 'logs',
                'rotation': '10 MB',
                'retention': '7 days'
            }
        })
        
        # Simulate some operations
        @monitor.track_sync_operation('example_account')
        async def sync_operation():
            await asyncio.sleep(1)
            monitor.track_file_operation('example_account', 'upload')
            return "Operation completed"
        
        await sync_operation()
        
        # Log some metrics
        monitor.log_metrics()
    
    asyncio.run(example())
