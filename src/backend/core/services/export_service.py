import os
import json
import tempfile
import threading
import time
from pathlib import Path
from typing import List, BinaryIO

from core.models.domain import PointCloudData, SegmentationResult, ObjectInfo
from infrastructure.storage.base import StorageService
from core.utils.app_utils import create_colored_ply, generate_metadata_json, create_zip_file, NumpyEncoder, get_obj_color
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

class ExportService:
    """Service for exporting and downloading results"""
    
    def __init__(self, storage_service: StorageService):
        self.storage_service = storage_service
    
    async def create_download_package(
        self,
        point_cloud_data: PointCloudData,
        segmentation_result: SegmentationResult,
        object_info: List[ObjectInfo],
        inference_engine=None
    ) -> BinaryIO:
        """Create a downloadable ZIP package with results"""
        logger.info("Creating download package")
        
        # Create a temporary directory for the zip files
        temp_dir = self.storage_service.get_temp_dir()
        
        try:
            # Create colored PLY file
            new_ply_path = await self._create_colored_ply_file(
                temp_dir, point_cloud_data, segmentation_result
            )
            
            # Generate metadata JSON
            json_path = await self._create_metadata_file(
                temp_dir, point_cloud_data, segmentation_result, object_info, inference_engine
            )
            
            # Create ZIP file
            zip_path = await self._create_zip_file(temp_dir, new_ply_path, json_path)
            
            # Return file stream
            return self._create_file_stream(zip_path, temp_dir)
            
        except Exception as e:
            # Clean up on error
            self.storage_service.cleanup_temp_files(temp_dir)
            raise e
    
    async def _create_colored_ply_file(
        self, 
        temp_dir: Path, 
        point_cloud_data: PointCloudData, 
        segmentation_result: SegmentationResult
    ) -> Path:
        """Create a PLY file with colored objects"""
        logger.info("Creating colored PLY file")
        
        new_ply_path = temp_dir / "scene_with_colored_objects.ply"
        
        create_colored_ply(
            coords=point_cloud_data.coords,
            colors=point_cloud_data.colors,
            mask=segmentation_result.mask,
            is_point_cloud=point_cloud_data.is_point_cloud,
            original_geometry_path=str(point_cloud_data.file_path),
            output_path=str(new_ply_path),
            get_obj_color_func=get_obj_color
        )
        
        if not new_ply_path.exists():
            raise FileNotFoundError(f"Failed to create PLY file at {new_ply_path}")
        
        logger.info(f"Created PLY file: {new_ply_path}, size: {new_ply_path.stat().st_size} bytes")
        return new_ply_path
    
    async def _create_metadata_file(
        self, 
        temp_dir: Path, 
        point_cloud_data: PointCloudData, 
        segmentation_result: SegmentationResult,
        object_info: List[ObjectInfo],
        inference_engine=None
    ) -> Path:
        """Create metadata JSON file"""
        logger.info("Generating metadata JSON")
        
        # Convert ObjectInfo list to dict format expected by generate_metadata_json
        object_info_dicts = []
        for obj in object_info:
            obj_dict = {
                'obj_id': obj.obj_id,
                'label': obj.label,
                'description': obj.description,
                'selected_views': obj.selected_views or [],
                'cost': obj.cost,
                'type': obj.type,
                'position': obj.position
            }
            object_info_dicts.append(obj_dict)
        
        metadata = generate_metadata_json(
            mask=segmentation_result.mask,
            new_ply_path=str(temp_dir / "scene_with_colored_objects.ply"),
            original_file_path=str(point_cloud_data.file_path),
            object_info=object_info_dicts,
            inference_obj=inference_engine,
            get_obj_color_func=get_obj_color
        )
        
        # Write the JSON file
        json_path = temp_dir / "metadata.json"
        with open(json_path, 'w') as f:
            json.dump(metadata, f, indent=2, cls=NumpyEncoder, ensure_ascii=False)
        
        if not json_path.exists():
            raise FileNotFoundError(f"Failed to create JSON file at {json_path}")
        
        logger.info(f"Created JSON file: {json_path}, size: {json_path.stat().st_size} bytes")
        return json_path
    
    async def _create_zip_file(self, temp_dir: Path, ply_path: Path, json_path: Path) -> Path:
        """Create ZIP file containing PLY and JSON"""
        logger.info("Creating ZIP file")
        
        zip_path = temp_dir / "segmentation_results.zip"
        files_to_zip = {
            str(ply_path): ply_path.name,
            str(json_path): "metadata.json"
        }
        
        create_zip_file(files_to_zip, str(zip_path))
        
        if not zip_path.exists():
            raise FileNotFoundError(f"Zip file was not created at {zip_path}")
        
        logger.info(f"Created ZIP file: {zip_path}, size: {zip_path.stat().st_size} bytes")
        return zip_path
    
    def _create_file_stream(self, zip_path: Path, temp_dir: Path) -> BinaryIO:
        """Create a file stream for download and schedule cleanup"""
        logger.info("Preparing file stream for download")
        
        def iterfile():
            with open(zip_path, 'rb') as f:
                chunk_size = 1024 * 1024  # 1MB chunks
                bytes_sent = 0
                while chunk := f.read(chunk_size):
                    bytes_sent += len(chunk)
                    yield chunk
                logger.info(f"Finished streaming {bytes_sent} bytes")
        
        # Schedule delayed cleanup
        def delayed_cleanup():
            time.sleep(10)  # Wait for download to complete
            self.storage_service.cleanup_temp_files(temp_dir)
        
        cleanup_thread = threading.Thread(target=delayed_cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
        # Return generator for streaming
        return iterfile()
    
    def get_download_info(self, zip_path: Path) -> dict:
        """Get information about the download file"""
        if not zip_path.exists():
            return {"exists": False}
        
        return {
            "exists": True,
            "size": zip_path.stat().st_size,
            "filename": "segmentation_results.zip"
        }
