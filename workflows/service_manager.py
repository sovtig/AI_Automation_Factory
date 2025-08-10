"""
System Service Manager for AI Automation Factory

Handles installation, removal, and management of the Drive Sync service.
"""
import os
import sys
import json
import time
import signal
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger
import psutil
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket

class DriveSyncService(win32serviceutil.ServiceFramework):
    """Windows Service for Drive Sync functionality."""
    
    _svc_name_ = "AIFactoryDriveSync"
    _svc_display_name_ = "AI Factory Drive Sync Service"
    _svc_description_ = "Manages synchronization between local files and Google Drive accounts"
    
    def __init__(self, args):
        """Initialize the service."""
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = False
        self.config = self._load_config()
        
        # Configure logging
        self._setup_logging()
        
        # Initialize DriveSync
        from workflows.drive_sync import DriveSync
        self.drive_sync = DriveSync()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load service configuration."""
        config_path = Path("config/drive_config.json")
        try:
            with open(config_path, 'r') as f:
                return json.load(f).get('system_service', {})
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def _setup_logging(self):
        """Configure logging for the service."""
        log_level = self.config.get('log_level', 'INFO')
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logger.add(
            log_dir / "drive_sync_service.log",
            rotation=f"10 MB",
            retention=f"{self.config.get('log_retention_days', 7)} days",
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
            backtrace=True,
            diagnose=True
        )
    
    def SvcStop(self):
        """Stop the service."""
        logger.info("Stopping Drive Sync service...")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.running = False
        win32event.SetEvent(self.stop_event)
    
    def SvcDoRun(self):
        """Run the service."""
        self.running = True
        logger.info("Starting Drive Sync service...")
        
        try:
            # Initialize and start the sync service
            import asyncio
            from workflows.drive_sync import DriveSync
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Start the sync service
            loop.run_until_complete(self.drive_sync.start())
            
            # Main service loop
            while self.running:
                # Check for stop event every second
                if win32event.WaitForSingleObject(self.stop_event, 1000) == win32event.WAIT_OBJECT_0:
                    logger.info("Stop event received, shutting down...")
                    break
                
                # Check if the service should be restarted
                if not self._is_sync_running():
                    logger.warning("Sync process not running, restarting...")
                    loop.run_until_complete(self._restart_sync())
            
            # Cleanup
            loop.run_until_complete(self.drive_sync.stop())
            loop.close()
            
        except Exception as e:
            logger.error(f"Service error: {e}", exc_info=True)
            self.SvcStop()
    
    async def _restart_sync(self) -> bool:
        """Restart the sync service."""
        try:
            await self.drive_sync.stop()
            await asyncio.sleep(5)  # Wait before restarting
            return await self.drive_sync.start()
        except Exception as e:
            logger.error(f"Failed to restart sync: {e}")
            return False
    
    def _is_sync_running(self) -> bool:
        """Check if the sync process is running."""
        # Check if the sync process is still responsive
        # This is a placeholder - implement actual process checking logic
        return True

class ServiceManager:
    """Manages the Windows service for Drive Sync."""
    
    @staticmethod
    def install() -> bool:
        """Install the service."""
        try:
            python_exe = sys.executable
            script_path = Path(__file__).resolve()
            
            # Register the service
            win32serviceutil.HandleCommandLine(
                svcClass=DriveSyncService,
                argv=[
                    'install',
                    '--startup=auto',  # Start automatically on boot
                    '--interactive',   # Allow interaction with desktop
                    '--description', DriveSyncService._svc_description_,
                    '--displayname', DriveSyncService._svc_display_name_,
                    '--python', python_exe,
                    '--params', 'run',
                    '--startup', 'auto',
                    '--stop-timeout', '60',
                    '--restart', 'on-failure',
                    '--restart-delay', '5s'
                ]
            )
            
            logger.info("Service installed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to install service: {e}")
            return False
    
    @staticmethod
    def uninstall() -> bool:
        """Uninstall the service."""
        try:
            win32serviceutil.HandleCommandLine(
                svcClass=DriveSyncService,
                argv=['remove']
            )
            logger.info("Service uninstalled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to uninstall service: {e}")
            return False
    
    @staticmethod
    def start() -> bool:
        """Start the service."""
        try:
            win32serviceutil.StartService(DriveSyncService._svc_name_)
            logger.info("Service started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            return False
    
    @staticmethod
    def stop() -> bool:
        """Stop the service."""
        try:
            win32serviceutil.StopService(DriveSyncService._svc_name_)
            logger.info("Service stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop service: {e}")
            return False
    
    @staticmethod
    def restart() -> bool:
        """Restart the service."""
        try:
            win32serviceutil.RestartService(DriveSyncService._svc_name_)
            logger.info("Service restarted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restart service: {e}")
            return False
    
    @staticmethod
    def status() -> Dict[str, Any]:
        """Get service status."""
        try:
            status = win32serviceutil.QueryServiceStatus(DriveSyncService._svc_name_)
            return {
                'service_name': DriveSyncService._svc_name_,
                'display_name': DriveSyncService._svc_display_name_,
                'status': 'running' if status[1] == win32service.SERVICE_RUNNING else 'stopped',
                'pid': status[8] if status[8] != 0 else None,
                'last_error': win32serviceutil.GetLastErrorText() or None
            }
            
        except Exception as e:
            return {
                'service_name': DriveSyncService._svc_name_,
                'status': 'not_installed',
                'error': str(e)
            }

def main():
    """Main entry point for the service manager."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Manage AI Factory Drive Sync Service')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Install command
    subparsers.add_parser('install', help='Install the service')
    
    # Uninstall command
    subparsers.add_parser('uninstall', help='Uninstall the service')
    
    # Start command
    subparsers.add_parser('start', help='Start the service')
    
    # Stop command
    subparsers.add_parser('stop', help='Stop the service')
    
    # Restart command
    subparsers.add_parser('restart', help='Restart the service')
    
    # Status command
    subparsers.add_parser('status', help='Check service status')
    
    # Run command (for service execution)
    run_parser = subparsers.add_parser('run', help='Run the service (internal use)')
    
    args = parser.parse_args()
    
    if args.command == 'install':
        ServiceManager.install()
    elif args.command == 'uninstall':
        ServiceManager.uninstall()
    elif args.command == 'start':
        ServiceManager.start()
    elif args.command == 'stop':
        ServiceManager.stop()
    elif args.command == 'restart':
        ServiceManager.restart()
    elif args.command == 'status':
        status = ServiceManager.status()
        print(json.dumps(status, indent=2))
    elif args.command == 'run':
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(DriveSyncService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        parser.print_help()

if __name__ == '__main__':
    if len(sys.argv) == 1:
        sys.argv.append('--help')
    
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
