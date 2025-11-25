import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO
try:
    import aiofiles
except ImportError:
    aiofiles = None

from infrastructure.storage.base import StorageService
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

class LocalStorageService(StorageService):
    """Local file system storage implementation"""
    
    def __init__(self, upload_dir: Path, output_dir: Path):
        self.upload_dir = Path(upload_dir)
        self.output_dir = Path(output_dir)
        
        # Ensure directories exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def save_upload(self, file_content: BinaryIO, filename: str) -> Path:
        """Save an uploaded file and return its path"""
        # Create a temporary directory for this upload
        temp_dir = self.get_temp_dir()
        file_path = temp_dir / filename
        
        # Save the file (use aiofiles if available, otherwise regular file I/O)
        content = file_content.read()
        if aiofiles:
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
        else:
            with open(file_path, 'wb') as f:
                f.write(content)
        
        logger.info(f"Saved uploaded file: {file_path}")
        return file_path
    
    def get_temp_dir(self) -> Path:
        """Get a temporary directory for processing"""
        temp_dir = Path(tempfile.mkdtemp(dir=self.upload_dir))
        logger.debug(f"Created temporary directory: {temp_dir}")
        return temp_dir
    
    def cleanup_temp_files(self, temp_dir: Path) -> None:
        """Clean up temporary files"""
        try:
            if temp_dir.exists() and temp_dir.is_dir():
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.debug(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory {temp_dir}: {e}")
    
    def file_exists(self, file_path: Path) -> bool:
        """Check if a file exists"""
        return file_path.exists() and file_path.is_file()
    
    def delete_file(self, file_path: Path) -> bool:
        """Delete a file"""
        try:
            if self.file_exists(file_path):
                file_path.unlink()
                logger.debug(f"Deleted file: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False
    
    def get_output_path(self, filename: str) -> Path:
        """Get path for output files"""
        return self.output_dir / filename
    
    def save_output_file(self, content: bytes, filename: str) -> Path:
        """Save content to an output file"""
        output_path = self.get_output_path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'wb') as f:
            f.write(content)
        
        logger.info(f"Saved output file: {output_path}")
        return output_path
