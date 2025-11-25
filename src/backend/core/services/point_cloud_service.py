from typing import Optional
import tempfile
import shutil
from pathlib import Path
from fastapi import UploadFile

from core.models.domain import PointCloudData, BoundingBox
from infrastructure.storage.base import StorageService
from utils_outer.file_utils import load_point_cloud_data
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

class PointCloudService:
    """Service for handling point cloud operations"""
    
    def __init__(self, storage_service: StorageService):
        self.storage_service = storage_service
    
    async def save_and_load_upload(self, file: UploadFile) -> PointCloudData:
        """Save uploaded file and load point cloud data"""
        logger.info(f"Processing uploaded file: {file.filename}")
        
        # Validate file
        if not file.filename.endswith('.ply'):
            raise ValueError("Only PLY files are supported")
        
        # Save uploaded file
        file_path = await self.storage_service.save_upload(file.file, file.filename)
        
        try:
            # Load point cloud data
            coords, colors, is_point_cloud = load_point_cloud_data(str(file_path))
            
            point_cloud_data = PointCloudData(
                coords=coords,
                colors=colors,
                is_point_cloud=is_point_cloud,
                point_count=len(coords),
                bounding_box=BoundingBox.from_coords(coords),
                file_path=file_path,
                filename=file.filename
            )
            
            logger.info(f"Loaded point cloud with {len(coords)} points")
            return point_cloud_data
            
        except Exception as e:
            # Clean up file if loading failed
            self.storage_service.delete_file(file_path)
            raise e
    
    def validate_point_cloud_file(self, filename: str) -> bool:
        """Validate if the file is a supported point cloud format"""
        return filename.lower().endswith('.ply')
    
    def get_point_cloud_info(self, point_cloud_data: PointCloudData) -> dict:
        """Get basic information about the point cloud"""
        return {
            "filename": point_cloud_data.filename,
            "point_count": point_cloud_data.point_count,
            "is_point_cloud": point_cloud_data.is_point_cloud,
            "bounding_box": {
                "min": point_cloud_data.bounding_box.min_coords,
                "max": point_cloud_data.bounding_box.max_coords
            }
        }
