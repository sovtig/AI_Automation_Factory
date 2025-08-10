"""
File Processing Pipeline for AI Automation Factory

Handles processing of files based on configured pipelines.
"""
import os
import re
import io
import json
import shutil
import zipfile
import tempfile
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import mimetypes

import pandas as pd
from PIL import Image
import pytesseract
from loguru import logger

from .monitoring import monitor, log_file_operation

@dataclass
class FileInfo:
    """Metadata about a file to be processed."""
    path: Path
    account: str
    pipeline: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def name(self) -> str:
        return self.path.name
    
    @property
    def suffix(self) -> str:
        return self.path.suffix.lower()
    
    @property
    def size(self) -> int:
        return self.path.stat().st_size
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': str(self.path),
            'account': self.account,
            'pipeline': self.pipeline,
            'metadata': self.metadata,
            'size': self.size,
            'modified': self.path.stat().st_mtime
        }

class FileProcessor:
    """Processes files based on configured pipelines."""
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """Initialize with configuration."""
        self.config_path = Path(config_path) if config_path else Path("config/drive_config.json")
        self.config = self._load_config()
        self.pipelines = self.config.get('file_processing', {}).get('pipelines', [])
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.processed_files = set()
        
        # Register file handlers
        self.handlers = {
            'image': self._process_image,
            'document': self._process_document,
            'spreadsheet': self._process_spreadsheet,
            'archive': self._process_archive,
            'pdf': self._process_pdf,
            'default': self._process_default
        }
        
        logger.info(f"Initialized FileProcessor with {len(self.pipelines)} pipelines")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def get_file_type(self, file_path: Union[str, Path]) -> str:
        """Determine the type of file."""
        path = Path(file_path)
        suffix = path.suffix.lower()
        
        # Common file type mappings
        image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        doc_exts = {'.doc', '.docx', '.odt', '.rtf', '.txt'}
        sheet_exts = {'.xls', '.xlsx', '.ods', '.csv'}
        archive_exts = {'.zip', '.rar', '.7z', '.tar', '.gz'}
        
        if suffix in image_exts:
            return 'image'
        elif suffix in doc_exts:
            return 'document'
        elif suffix in sheet_exts:
            return 'spreadsheet'
        elif suffix in archive_exts:
            return 'archive'
        elif suffix == '.pdf':
            return 'pdf'
        else:
            return 'default'
    
    def find_matching_pipelines(self, file_info: FileInfo) -> List[Dict[str, Any]]:
        """Find all pipelines that match the given file."""
        matching = []
        
        for pipeline in self.pipelines:
            # Check file patterns
            patterns = pipeline.get('file_patterns', [])
            if not any(self._matches_pattern(file_info.name, p) for p in patterns):
                continue
                
            # Check source folders if specified
            source_folders = pipeline.get('source_folders', [])
            if source_folders and not any(
                str(file_info.path).startswith(f) for f in source_folders
            ):
                continue
                
            matching.append(pipeline)
        
        return matching
    
    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if filename matches the given pattern."""
        # Convert pattern to regex
        regex = pattern.replace('.', '\.').replace('*', '.*').replace('?', '.')
        return bool(re.fullmatch(regex, filename, re.IGNORECASE))
    
    async def process_file(self, file_path: Union[str, Path], account: str) -> bool:
        """Process a single file using matching pipelines."""
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return False
        
        file_info = FileInfo(path=file_path, account=account, pipeline='')
        pipelines = self.find_matching_pipelines(file_info)
        
        if not pipelines:
            logger.debug(f"No matching pipelines for {file_path}")
            return False
        
        success = True
        for pipeline in pipelines:
            pipeline_name = pipeline.get('name', 'unknown')
            logger.info(f"Processing {file_path} with pipeline: {pipeline_name}")
            
            try:
                file_info.pipeline = pipeline_name
                result = await self._process_with_pipeline(file_info, pipeline)
                
                if not result:
                    success = False
                    logger.warning(f"Pipeline {pipeline_name} failed for {file_path}")
                else:
                    log_file_operation(account, f"processed_{pipeline_name}")
                    
            except Exception as e:
                success = False
                logger.error(f"Error processing {file_path} with {pipeline_name}: {e}")
                monitor.log_error(
                    f"Pipeline {pipeline_name} failed",
                    exc_info=e,
                    extra={
                        'file': str(file_path),
                        'account': account,
                        'pipeline': pipeline_name
                    }
                )
        
        return success
    
    async def _process_with_pipeline(self, file_info: FileInfo, pipeline: Dict[str, Any]) -> bool:
        """Process a file using the specified pipeline."""
        file_type = self.get_file_type(file_info.path)
        handler = self.handlers.get(file_type, self.handlers['default'])
        
        try:
            # Create output directory if needed
            output_dir = pipeline.get('output_dir', 'processed')
            output_path = Path(output_dir) / file_info.path.name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Process the file
            result = await handler(file_info, pipeline, output_path)
            
            # Handle post-processing
            if result and pipeline.get('move_processed_to'):
                self._move_processed_file(file_info, pipeline)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in {pipeline.get('name')} pipeline: {e}")
            return False
    
    async def _process_image(self, file_info: FileInfo, pipeline: Dict[str, Any], 
                           output_path: Path) -> bool:
        """Process an image file."""
        try:
            with Image.open(file_info.path) as img:
                # Apply transformations
                if pipeline.get('resize'):
                    width, height = pipeline['resize']
                    img = img.resize((width, height), Image.Resampling.LANCZOS)
                
                # Compress if needed
                quality = pipeline.get('compression_quality', 85)
                
                # Save the processed image
                img.save(
                    output_path,
                    quality=quality,
                    optimize=True,
                    **img.info
                )
                
                # OCR if requested
                if pipeline.get('perform_ocr', False):
                    text = pytesseract.image_to_string(img)
                    text_path = output_path.with_suffix('.txt')
                    with open(text_path, 'w', encoding='utf-8') as f:
                        f.write(text)
            
            return True
            
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            return False
    
    async def _process_document(self, file_info: FileInfo, pipeline: Dict[str, Any],
                              output_path: Path) -> bool:
        """Process a document file."""
        # Implementation depends on document type
        # This is a placeholder - actual implementation would use libraries like python-docx
        try:
            shutil.copy2(file_info.path, output_path)
            return True
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            return False
    
    async def _process_spreadsheet(self, file_info: FileInfo, pipeline: Dict[str, Any],
                                 output_path: Path) -> bool:
        """Process a spreadsheet file."""
        try:
            # Read the spreadsheet
            if file_info.path.suffix.lower() == '.csv':
                df = pd.read_csv(file_info.path)
            else:
                df = pd.read_excel(file_info.path)
            
            # Apply transformations
            for operation in pipeline.get('operations', []):
                if operation.get('type') == 'pandas':
                    # Execute pandas operation
                    local_vars = {'df': df, 'pd': pd}
                    exec(operation['script'], globals(), local_vars)
                    df = local_vars['df']
            
            # Save the result
            output_format = pipeline.get('output_format', 'parquet')
            if output_format == 'parquet':
                df.to_parquet(output_path.with_suffix('.parquet'))
            elif output_format == 'csv':
                df.to_csv(output_path.with_suffix('.csv'), index=False)
            else:
                df.to_excel(output_path.with_suffix('.xlsx'), index=False)
            
            return True
            
        except Exception as e:
            logger.error(f"Spreadsheet processing failed: {e}")
            return False
    
    async def _process_archive(self, file_info: FileInfo, pipeline: Dict[str, Any],
                             output_path: Path) -> bool:
        """Process an archive file."""
        try:
            extract_to = pipeline.get('extract_to', 'extracted')
            extract_path = Path(extract_to) / file_info.path.stem
            extract_path.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(file_info.path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            
            # Process extracted files
            if pipeline.get('process_extracted', False):
                for extracted_file in extract_path.rglob('*'):
                    if extracted_file.is_file():
                        await self.process_file(extracted_file, file_info.account)
            
            # Delete original if requested
            if pipeline.get('delete_after_extraction', False):
                file_info.path.unlink()
            
            return True
            
        except Exception as e:
            logger.error(f"Archive processing failed: {e}")
            return False
    
    async def _process_pdf(self, file_info: FileInfo, pipeline: Dict[str, Any],
                         output_path: Path) -> bool:
        """Process a PDF file."""
        try:
            # Simple copy for now - could add OCR, text extraction, etc.
            shutil.copy2(file_info.path, output_path)
            
            # Extract text if requested
            if pipeline.get('extract_text', False):
                try:
                    import PyPDF2
                    
                    with open(file_info.path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        text = ""
                        for page in reader.pages:
                            text += page.extract_text() + "\n"
                    
                    text_path = output_path.with_suffix('.txt')
                    with open(text_path, 'w', encoding='utf-8') as f:
                        f.write(text)
                        
                except ImportError:
                    logger.warning("PyPDF2 not installed, skipping text extraction")
            
            return True
            
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            return False
    
    async def _process_default(self, file_info: FileInfo, pipeline: Dict[str, Any],
                             output_path: Path) -> bool:
        """Default file processor."""
        try:
            shutil.copy2(file_info.path, output_path)
            return True
        except Exception as e:
            logger.error(f"Default processing failed: {e}")
            return False
    
    def _move_processed_file(self, file_info: FileInfo, pipeline: Dict[str, Any]) -> None:
        """Move a processed file to the specified location."""
        try:
            dest_dir = Path(pipeline['move_processed_to'])
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            dest_path = dest_dir / file_info.path.name
            
            # Handle naming conflicts
            counter = 1
            while dest_path.exists():
                name = f"{file_info.path.stem}_{counter}{file_info.path.suffix}"
                dest_path = dest_dir / name
                counter += 1
            
            shutil.move(file_info.path, dest_path)
            logger.info(f"Moved processed file to {dest_path}")
            
        except Exception as e:
            logger.error(f"Failed to move processed file: {e}")
    
    async def process_directory(self, directory: Union[str, Path], account: str) -> Dict[str, Any]:
        """Process all files in a directory."""
        directory = Path(directory)
        if not directory.is_dir():
            logger.error(f"Directory not found: {directory}")
            return {'success': False, 'processed': 0, 'errors': 0}
        
        processed = 0
        errors = 0
        
        # Process files in parallel
        futures = []
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                futures.append(
                    self.executor.submit(
                        self.process_file,
                        file_path,
                        account
                    )
                )
        
        # Wait for all tasks to complete
        for future in as_completed(futures):
            try:
                if future.result():
                    processed += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                logger.error(f"Error processing file: {e}")
        
        return {
            'success': errors == 0,
            'processed': processed,
            'errors': errors
        }

# Example usage
async def example():
    # Initialize processor
    processor = FileProcessor()
    
    # Process a single file
    await processor.process_file('path/to/file.pdf', 'xy_drive_3')
    
    # Process a directory
    result = await processor.process_directory('path/to/directory', 'xy_drive_4')
    print(f"Processed {result['processed']} files with {result['errors']} errors")

if __name__ == "__main__":
    import asyncio
    asyncio.run(example())
