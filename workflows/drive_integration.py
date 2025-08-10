"""
Google Drive Integration for AI Automation Factory

Handles file operations across multiple Google Drive accounts using xydrive.
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field
from loguru import logger
import asyncio
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io

# If modifying these scopes, delete the token.json file
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.metadata'
]

@dataclass
class DriveAccount:
    """Represents a Google Drive account configuration."""
    name: str
    credentials_path: Path
    token_path: Optional[Path] = None
    credentials: Optional[Credentials] = None
    service: Any = None
    
    def __post_init__(self):
        if not self.token_path:
            self.token_path = self.credentials_path.parent / f"{self.name}_token.json"

class DriveManager:
    """Manages multiple Google Drive accounts and operations."""
    
    def __init__(self, config_dir: Union[str, Path] = "./config"):
        """Initialize with directory containing credentials."""
        self.config_dir = Path(config_dir)
        self.accounts: Dict[str, DriveAccount] = {}
        self.default_account: Optional[str] = None
        logger.info(f"Initialized DriveManager with config directory: {self.config_dir}")
    
    async def add_account(self, name: str, credentials_file: str, token_file: Optional[str] = None) -> bool:
        """Add a Google Drive account."""
        try:
            creds_path = self.config_dir / credentials_file
            token_path = self.config_dir / token_file if token_file else None
            
            if not creds_path.exists():
                logger.error(f"Credentials file not found: {creds_path}")
                return False
                
            self.accounts[name] = DriveAccount(
                name=name,
                credentials_path=creds_path,
                token_path=token_path
            )
            
            if not self.default_account:
                self.default_account = name
                
            logger.info(f"Added Google Drive account: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding account {name}: {e}")
            return False
    
    async def authenticate(self, account_name: Optional[str] = None) -> bool:
        """Authenticate with Google Drive API."""
        account = self._get_account(account_name)
        if not account:
            return False
            
        try:
            creds = None
            
            # Load existing credentials if they exist
            if account.token_path.exists():
                creds = Credentials.from_authorized_user_file(
                    str(account.token_path), SCOPES)
            
            # If there are no (valid) credentials, let the user log in
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(account.credentials_path), SCOPES)
                    creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                with open(account.token_path, 'w') as token:
                    token.write(creds.to_json())
            
            account.credentials = creds
            account.service = build('drive', 'v3', credentials=creds)
            logger.info(f"Authenticated with Google Drive account: {account.name}")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed for {account.name}: {e}")
            return False
    
    def _get_account(self, account_name: Optional[str] = None) -> Optional[DriveAccount]:
        """Get account by name or return default."""
        name = account_name or self.default_account
        if not name or name not in self.accounts:
            logger.error(f"No account found: {name}")
            return None
        return self.accounts[name]
    
    async def upload_file(self, local_path: Union[str, Path], 
                         drive_folder_id: Optional[str] = None,
                         account_name: Optional[str] = None) -> Optional[Dict]:
        """Upload a file to Google Drive."""
        account = self._get_account(account_name)
        if not account or not account.service:
            return None
            
        try:
            local_path = Path(local_path)
            file_metadata = {
                'name': local_path.name,
                'mimeType': 'application/octet-stream'
            }
            
            if drive_folder_id:
                file_metadata['parents'] = [drive_folder_id]
            
            media = MediaFileUpload(
                str(local_path),
                mimetype='application/octet-stream',
                resumable=True
            )
            
            file = account.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, mimeType, webViewLink, webContentLink, size'
            ).execute()
            
            logger.info(f"Uploaded {local_path} to {account.name}")
            return file
            
        except Exception as e:
            logger.error(f"Error uploading {local_path} to {account.name}: {e}")
            return None
    
    async def download_file(self, file_id: str, 
                           local_path: Union[str, Path],
                           account_name: Optional[str] = None) -> bool:
        """Download a file from Google Drive."""
        account = self._get_account(account_name)
        if not account or not account.service:
            return False
            
        try:
            local_path = Path(local_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            request = account.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                logger.info(f"Download {int(status.progress() * 100)}%")
            
            with open(local_path, 'wb') as f:
                f.write(fh.getvalue())
                
            logger.info(f"Downloaded {file_id} to {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading {file_id} from {account.name}: {e}")
            return False
    
    async def list_files(self, query: str = "", 
                        account_name: Optional[str] = None) -> List[Dict]:
        """List files in Google Drive."""
        account = self._get_account(account_name)
        if not account or not account.service:
            return []
            
        try:
            results = []
            page_token = None
            
            while True:
                response = account.service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, mimeType, size, modifiedTime)',
                    pageToken=page_token
                ).execute()
                
                results.extend(response.get('files', []))
                page_token = response.get('nextPageToken')
                
                if not page_token:
                    break
                    
            logger.info(f"Found {len(results)} files in {account.name}")
            return results
            
        except Exception as e:
            logger.error(f"Error listing files in {account.name}: {e}")
            return []

# Example usage
async def example():
    # Initialize manager
    manager = DriveManager("./config")
    
    # Add accounts (credentials files should be in the config directory)
    await manager.add_account("main", "credentials_main.json")
    await manager.add_account("backup", "credentials_backup.json")
    
    # Authenticate
    await manager.authenticate("main")
    
    # Upload a file
    await manager.upload_file("data/important.txt", "folder_id_here")
    
    # List files
    files = await manager.list_files("name contains 'important'")
    print(f"Found files: {files}")
    
    # Download a file
    if files:
        await manager.download_file(files[0]['id'], "downloads/important_backup.txt")

if __name__ == "__main__":
    asyncio.run(example())
