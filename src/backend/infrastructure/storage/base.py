from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

class StorageService(ABC):
    """Abstract base class for storage services"""
    
    @abstractmethod
    async def save_upload(self, file_content: BinaryIO, filename: str) -> Path:
        """Save an uploaded file and return its path"""
        pass
    
    @abstractmethod
    def get_temp_dir(self) -> Path:
        """Get a temporary directory for processing"""
        pass
    
    @abstractmethod
    def cleanup_temp_files(self, temp_dir: Path) -> None:
        """Clean up temporary files"""
        pass
    
    @abstractmethod
    def file_exists(self, file_path: Path) -> bool:
        """Check if a file exists"""
        pass
    
    @abstractmethod
    def delete_file(self, file_path: Path) -> bool:
        """Delete a file"""
        pass
