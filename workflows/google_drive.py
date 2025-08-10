"""
Google Drive Integration for AI Automation Factory

This module provides functionality to interact with Google Drive API for file storage and sharing.
"""
import os
import io
from typing import Optional, Union, List, Dict, Any, BinaryIO
from pathlib import Path
from datetime import datetime, timedelta
import logging
from loguru import logger

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload
    from googleapiclient.errors import HttpError
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    logger.warning("Google Drive API libraries not available. Google Drive functionality will be limited.")

class GoogleDriveManager:
    """Manages interactions with Google Drive API."""
    
    # Define the scopes for Google Drive API
    SCOPES = [
        'https://www.googleapis.com/auth/drive.file',  # Per-file access
        'https://www.googleapis.com/auth/drive.metadata',  # View metadata
    ]
    
    def __init__(self, credentials_file: str = 'credentials.json', token_file: str = 'token.json'):
        """
        Initialize the Google Drive manager.
        
        Args:
            credentials_file: Path to the Google API credentials file
            token_file: Path to store the authentication token
        """
        if not GOOGLE_DRIVE_AVAILABLE:
            raise RuntimeError("Google Drive API libraries are not available. Please install google-api-python-client and google-auth-oauthlib.")
            
        self.credentials_file = Path(credentials_file)
        self.token_file = Path(token_file)
        self.credentials = None
        self.service = None
        self.logger = logger.bind(component="GoogleDriveManager")
        
    def authenticate(self) -> bool:
        """
        Authenticate with Google Drive API.
        
        Returns:
            bool: True if authentication was successful, False otherwise
        """
        self.credentials = None
        
        # Check if token exists
        if self.token_file.exists():
            try:
                self.credentials = Credentials.from_authorized_user_file(
                    str(self.token_file), self.SCOPES)
                self.logger.info("Loaded credentials from token file")
            except Exception as e:
                self.logger.error(f"Error loading credentials: {str(e)}")
                return False
        
        # If there are no (valid) credentials available, let the user log in
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                try:
                    self.credentials.refresh(Request())
                    self.logger.info("Refreshed expired credentials")
                except Exception as e:
                    self.logger.error(f"Error refreshing token: {str(e)}")
                    return False
            else:
                if not self.credentials_file.exists():
                    self.logger.error(f"Credentials file not found: {self.credentials_file}")
                    return False
                    
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_file), self.SCOPES)
                    self.credentials = flow.run_local_server(port=0)
                    self.logger.info("Obtained new credentials")
                except Exception as e:
                    self.logger.error(f"Error obtaining new credentials: {str(e)}")
                    return False
            
            # Save the credentials for the next run
            try:
                with open(self.token_file, 'w') as token:
                    token.write(self.credentials.to_json())
                self.logger.info(f"Saved credentials to {self.token_file}")
            except Exception as e:
                self.logger.error(f"Error saving credentials: {str(e)}")
                return False
        
        # Create the Drive API service
        try:
            self.service = build('drive', 'v3', credentials=self.credentials)
            return True
        except Exception as e:
            self.logger.error(f"Error creating Drive service: {str(e)}")
            return False
    
    async def upload_file(
        self,
        file_path: Union[str, Path],
        folder_id: Optional[str] = None,
        mime_type: str = 'application/octet-stream',
        description: str = ''
    ) -> Optional[Dict[str, Any]]:
        """
        Upload a file to Google Drive.
        
        Args:
            file_path: Path to the file to upload
            folder_id: ID of the folder to upload to (None for root)
            mime_type: MIME type of the file
            description: Optional file description
            
        Returns:
            Dictionary with file metadata if successful, None otherwise
        """
        if not self.service:
            if not self.authenticate():
                return None
                
        file_path = Path(file_path)
        if not file_path.exists() or not file_path.is_file():
            self.logger.error(f"File not found: {file_path}")
            return None
            
        file_metadata = {
            'name': file_path.name,
            'description': description,
            'mimeType': mime_type
        }
        
        if folder_id:
            file_metadata['parents'] = [folder_id]
            
        try:
            media = MediaFileUpload(
                str(file_path),
                mimetype=mime_type,
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,webViewLink,mimeType,size,modifiedTime,createdTime,md5Checksum',
                supportsAllDrives=True
            ).execute()
            
            self.logger.info(f"Uploaded file: {file_path.name} (ID: {file.get('id')})")
            return file
            
        except HttpError as error:
            self.logger.error(f"An error occurred while uploading {file_path.name}: {str(error)}")
            return None
            
    async def download_file(
        self,
        file_id: str,
        output_path: Union[str, Path],
        mime_type: str = 'application/octet-stream'
    ) -> bool:
        """
        Download a file from Google Drive.
        
        Args:
            file_id: ID of the file to download
            output_path: Path to save the downloaded file
            mime_type: MIME type of the file
            
        Returns:
            bool: True if download was successful, False otherwise
        """
        if not self.service:
            if not self.authenticate():
                return False
                
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_handle = io.BytesIO()
            downloader = MediaIoBaseDownload(file_handle, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                self.logger.info(f"Download {int(status.progress() * 100)}%")
                
            with open(output_path, 'wb') as f:
                file_handle.seek(0)
                f.write(file_handle.read())
                
            self.logger.info(f"Downloaded file to {output_path}")
            return True
            
        except HttpError as error:
            self.logger.error(f"An error occurred while downloading file {file_id}: {str(error)}")
            return False
            
    async def list_files(
        self,
        query: str = "trashed=false",
        fields: str = "files(id, name, mimeType, modifiedTime, size)",
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List files in Google Drive.
        
        Args:
            query: Query string to filter files (see Google Drive API docs)
            fields: Fields to include in the response
            page_size: Number of files to return per page
            
        Returns:
            List of file metadata dictionaries
        """
        if not self.service:
            if not self.authenticate():
                return []
                
        try:
            results = self.service.files().list(
                q=query,
                pageSize=page_size,
                fields=f"nextPageToken, {fields}",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="allDrives"
            ).execute()
            
            files = results.get('files', [])
            self.logger.info(f"Found {len(files)} files matching query")
            return files
            
        except HttpError as error:
            self.logger.error(f"An error occurred while listing files: {str(error)}")
            return []
            
    async def create_folder(
        self,
        name: str,
        parent_id: Optional[str] = None,
        description: str = ''
    ) -> Optional[Dict[str, Any]]:
        """
        Create a folder in Google Drive.
        
        Args:
            name: Name of the folder to create
            parent_id: ID of the parent folder (None for root)
            description: Optional folder description
            
        Returns:
            Dictionary with folder metadata if successful, None otherwise
        """
        if not self.service:
            if not self.authenticate():
                return None
                
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
            'description': description
        }
        
        if parent_id:
            file_metadata['parents'] = [parent_id]
            
        try:
            folder = self.service.files().create(
                body=file_metadata,
                fields='id,name,webViewLink,mimeType,modifiedTime,createdTime',
                supportsAllDrives=True
            ).execute()
            
            self.logger.info(f"Created folder: {name} (ID: {folder.get('id')})")
            return folder
            
        except HttpError as error:
            self.logger.error(f"An error occurred while creating folder {name}: {str(error)}")
            return None
            
    async def delete_file(self, file_id: str) -> bool:
        """
        Delete a file or folder from Google Drive.
        
        Args:
            file_id: ID of the file/folder to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        if not self.service:
            if not self.authenticate():
                return False
                
        try:
            self.service.files().delete(
                fileId=file_id,
                supportsAllDrives=True
            ).execute()
            
            self.logger.info(f"Deleted file/folder with ID: {file_id}")
            return True
            
        except HttpError as error:
            self.logger.error(f"An error occurred while deleting file {file_id}: {str(error)}")
            return False

    async def search_files(
        self,
        name: Optional[str] = None,
        mime_type: Optional[str] = None,
        folder_id: Optional[str] = None,
        modified_after: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for files in Google Drive.
        
        Args:
            name: Partial or full filename to search for
            mime_type: MIME type to filter by
            folder_id: Search within a specific folder
            modified_after: Only return files modified after this date
            
        Returns:
            List of file metadata dictionaries
        """
        query_parts = ["trashed=false"]
        
        if name:
            query_parts.append(f"name contains '{name}'")
        if mime_type:
            query_parts.append(f"mimeType='{mime_type}'")
        if folder_id:
            query_parts.append(f"'{folder_id}' in parents")
        if modified_after:
            # Format as RFC 3339 timestamp
            time_str = modified_after.strftime('%Y-%m-%dT%H:%M:%S')
            query_parts.append(f"modifiedTime > '{time_str}'")
            
        query = ' and '.join(query_parts)
        return await self.list_files(query=query)

# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Initialize the Google Drive manager
        drive = GoogleDriveManager(
            credentials_file='credentials.json',
            token_file='token.json'
        )
        
        # Authenticate
        if not drive.authenticate():
            print("Authentication failed")
            return
            
        # List files in root
        files = await drive.list_files()
        print(f"Found {len(files)} files in root")
        
        # Create a test folder
        folder = await drive.create_folder("Test Folder")
        if folder:
            print(f"Created folder: {folder['name']} (ID: {folder['id']})")
            
            # Upload a test file to the folder
            with open('test.txt', 'w') as f:
                f.write("This is a test file.")
                
            uploaded_file = await drive.upload_file(
                'test.txt',
                folder_id=folder['id']
            )
            
            if uploaded_file:
                print(f"Uploaded file: {uploaded_file['name']}")
    
    asyncio.run(main())
