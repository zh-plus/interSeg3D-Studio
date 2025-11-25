import numpy as np
import open3d as o3d
from pathlib import Path
from typing import Tuple

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

def load_point_cloud_data(file_path: str) -> Tuple[np.ndarray, np.ndarray, bool]:
    """
    Load point cloud data from a PLY file
    
    Args:
        file_path (str): Path to the PLY file
    
    Returns:
        tuple: (coords, colors, is_point_cloud)
    """
    file_path = str(file_path)

    logger.info(f"Loading point cloud data from: {file_path}")
    
    pcd_type = o3d.io.read_file_geometry_type(file_path)
    if pcd_type == o3d.io.FileGeometry.CONTAINS_TRIANGLES:
        logger.info("File contains triangles, loading as mesh")
        geometry = o3d.io.read_triangle_mesh(file_path)
        coords = np.array(geometry.vertices)
        colors = np.array(geometry.vertex_colors) if geometry.has_vertex_colors() else np.ones((len(coords), 3)) * 0.5
        is_point_cloud = False
        logger.info(f"Loaded mesh with {len(coords)} vertices")
    else:
        logger.info("File contains points, loading as point cloud")
        geometry = o3d.io.read_point_cloud(file_path)
        coords = np.array(geometry.points)
        colors = np.array(geometry.colors) if geometry.has_colors() else np.ones((len(coords), 3)) * 0.5
        is_point_cloud = True
        logger.info(f"Loaded point cloud with {len(coords)} points")
    
    return coords, colors, is_point_cloud

def validate_file_extension(filename: str, allowed_extensions: list) -> bool:
    """
    Validate if the file has an allowed extension
    
    Args:
        filename (str): Name of the file
        allowed_extensions (list): List of allowed extensions (e.g., ['.ply', '.pcd'])
    
    Returns:
        bool: True if extension is allowed
    """
    file_ext = Path(filename).suffix.lower()
    return file_ext in [ext.lower() for ext in allowed_extensions]

def get_file_size_mb(file_path: Path) -> float:
    """
    Get file size in megabytes
    
    Args:
        file_path (Path): Path to the file
    
    Returns:
        float: File size in MB
    """
    try:
        size_bytes = file_path.stat().st_size
        return size_bytes / (1024 * 1024)
    except Exception as e:
        logger.error(f"Error getting file size for {file_path}: {e}")
        return 0.0

def ensure_directory_exists(directory: Path) -> None:
    """
    Ensure a directory exists, create if it doesn't
    
    Args:
        directory (Path): Directory path
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {directory}")
    except Exception as e:
        logger.error(f"Failed to create directory {directory}: {e}")
        raise
