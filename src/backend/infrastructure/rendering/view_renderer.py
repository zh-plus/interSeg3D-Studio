from typing import List
from pathlib import Path
import numpy as np

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

class ViewRenderer:
    """Service for rendering views of 3D objects"""
    
    def __init__(self):
        pass
    
    def render_object_views(
        self,
        point_cloud_path: str,
        mask: np.ndarray,
        obj_id: int,
        output_dir: str,
        num_positions: int = 8,
        mask_mode: str = "outline"
    ) -> List[str]:
        """
        Render multiple views of a masked object
        
        Args:
            point_cloud_path: Path to the point cloud file
            mask: Segmentation mask
            obj_id: Object ID to render
            output_dir: Directory to save rendered views
            num_positions: Number of camera positions
            mask_mode: How to display the mask ("outline" or "full")
        
        Returns:
            List of paths to rendered view images
        """
        logger.info(f"Rendering {num_positions} views for object {obj_id}")
        
        try:
            # Import here to avoid circular imports and ensure the module is available
            from infrastructure.rendering.utils import test_camera_positions
            
            view_paths = test_camera_positions(
                point_cloud_path=point_cloud_path,
                mask=mask,
                output_dir=output_dir,
                view_angle=90.0,
                distance_factor=1,
                num_positions=num_positions,
                camera_height=1.5,
                mask_mode=mask_mode,
                obj_id=obj_id,
            )
            
            logger.info(f"Successfully rendered {len(view_paths)} views")
            return view_paths
            
        except Exception as e:
            logger.error(f"Error rendering views for object {obj_id}: {e}")
            raise e
    
    def get_render_settings(self) -> dict:
        """Get current rendering settings"""
        return {
            "default_num_positions": 8,
            "default_mask_mode": "outline",
            "default_view_angle": 90.0,
            "default_distance_factor": 1,
            "default_camera_height": 1.5
        }
