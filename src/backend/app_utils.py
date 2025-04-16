import json
import os
import zipfile

import numpy as np
import open3d as o3d

from logger import get_logger

logger = get_logger("app_utils")


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for numpy/torch types"""

    def default(self, obj):
        if isinstance(obj, (np.integer, np.int_)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float_)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if hasattr(obj, 'item'):  # For torch tensors
            return obj.item()
        return super().default(obj)


def create_colored_ply(coords, colors, mask, is_point_cloud, original_geometry_path, output_path, get_obj_color_func):
    """
    Creates a PLY file with uncolored scene (neutral gray) and colored objects

    Args:
        coords (np.ndarray): Point/vertex coordinates
        colors (np.ndarray): Original point/vertex colors (not used, kept for reference)
        mask (np.ndarray): Segmentation mask with object IDs
        is_point_cloud (bool): Whether the geometry is a point cloud or mesh
        original_geometry_path (str): Path to the original geometry file (for mesh triangles)
        output_path (str): Path to save the output PLY file
        get_obj_color_func (callable): Function to get object color based on ID

    Returns:
        str: Path to the saved PLY file
    """
    # Create a new color array with background as neutral gray and objects colored
    new_colors = np.ones((len(coords), 3)) * 0.7  # Default scene color (light gray)

    # Apply object colors based on mask
    unique_obj_ids = np.unique(mask)
    logger.info(f"Coloring {len(unique_obj_ids)} unique object IDs")

    for obj_id in unique_obj_ids:
        if obj_id > 0:  # Skip background
            obj_mask = mask == obj_id
            obj_color = get_obj_color_func(obj_id, normalize=True)
            new_colors[obj_mask] = obj_color
            logger.info(f"Applied color to object {obj_id}: {np.sum(obj_mask)} points")

    # Create a new geometry with these colors
    if not is_point_cloud:
        # It's a mesh
        logger.info(f"Processing as mesh: {original_geometry_path}")
        original_mesh = o3d.io.read_triangle_mesh(original_geometry_path)
        new_geometry = o3d.geometry.TriangleMesh()
        new_geometry.vertices = o3d.utility.Vector3dVector(coords)
        new_geometry.vertex_colors = o3d.utility.Vector3dVector(new_colors)
        new_geometry.triangles = original_mesh.triangles
        new_geometry.compute_vertex_normals()
        o3d.io.write_triangle_mesh(output_path, new_geometry)
    else:
        # It's a point cloud
        logger.info(f"Processing as point cloud: {original_geometry_path}")
        new_geometry = o3d.geometry.PointCloud()
        new_geometry.points = o3d.utility.Vector3dVector(coords)
        new_geometry.colors = o3d.utility.Vector3dVector(new_colors)
        o3d.io.write_point_cloud(output_path, new_geometry)

    logger.info(f"Created colored geometry file: {output_path}")
    return output_path


def generate_metadata_json(mask, new_ply_path, original_file_path, object_info, inference_obj, get_obj_color_func):
    """
    Generate JSON metadata for segmentation results

    Args:
        mask (np.ndarray): Segmentation mask with object IDs
        new_ply_path (str): Path to the new PLY file
        original_file_path (str): Path to the original file
        object_info (list): List of object recognition results
        inference_obj: Inference object with click handler
        get_obj_color_func (callable): Function to get object color based on ID

    Returns:
        dict: Metadata dictionary
    """
    logger.info("Generating metadata JSON")

    metadata = {
        "objects": [],
        "file_info": {
            "ply_file": os.path.basename(new_ply_path),
            "original_file": os.path.basename(original_file_path)
        }
    }

    # Add object information from recognition results if available
    if object_info:
        logger.info(f"Adding object info from recognition results: {len(object_info)} objects")
        for obj_info in object_info:
            # Extract object ID (usually in the 'label' field or from the order)
            obj_id = None
            if 'obj_id' in obj_info:
                obj_id = obj_info['obj_id']
            else:
                # Try to extract ID from label (e.g., "Object 1" -> 1)
                label = obj_info.get('label', '')
                import re
                match = re.search(r'\d+', label)
                if match:
                    obj_id = int(match.group())

            if obj_id is None:
                # If ID extraction failed, use index+1 as ID
                obj_id = len(metadata["objects"]) + 1

            obj_color = get_obj_color_func(obj_id, normalize=True)

            # Convert numpy values to Python native types for JSON serialization
            if hasattr(obj_color, 'tolist'):
                obj_color = obj_color.tolist()

            # Create object data excluding selected_views
            obj_data = {
                "id": int(obj_id),
                "label": obj_info.get("label", f"Object {obj_id}"),
                "description": obj_info.get("description", ""),
                "color": obj_color
            }

            # Add cost information if available
            if "cost" in obj_info:
                obj_data["cost"] = float(obj_info["cost"])

            metadata["objects"].append(obj_data)
            logger.info(f"Added object {obj_id} to metadata")
    else:
        # If no object info, include basic information based on the mask
        logger.info("No object info available, creating basic metadata from mask")
        unique_obj_ids = np.unique(mask)
        for obj_id in unique_obj_ids:
            if obj_id > 0:  # Skip background
                obj_color = get_obj_color_func(obj_id, normalize=True)
                if hasattr(obj_color, 'tolist'):
                    obj_color = obj_color.tolist()

                metadata["objects"].append({
                    "id": int(obj_id),
                    "label": f"Object {obj_id}",
                    "color": obj_color
                })
                logger.info(f"Added basic object {obj_id} to metadata")

    # Add click information if available
    if inference_obj and inference_obj.click_handler:
        logger.info("Adding click data to metadata")
        click_data = []
        for click in inference_obj.click_handler.clicks:
            # Convert click to dict and ensure values are JSON serializable
            click_dict = {}
            raw_dict = click.to_dict()

            for k, v in raw_dict.items():
                # Convert any numpy/torch values to Python native types
                if hasattr(v, 'tolist'):
                    click_dict[k] = v.tolist()
                elif hasattr(v, 'item'):
                    click_dict[k] = v.item()
                else:
                    click_dict[k] = v

            click_data.append(click_dict)

        metadata["click_data"] = click_data
        logger.info(f"Added {len(click_data)} clicks to metadata")

    # Count points per object from the mask
    unique_values, counts = np.unique(mask, return_counts=True)
    object_counts = {}
    for i, val in enumerate(unique_values):
        if val > 0:  # Skip background
            object_counts[int(val)] = int(counts[i])

    metadata["object_counts"] = object_counts
    logger.info(f"Added point counts for {len(object_counts)} objects to metadata")

    return metadata


def create_zip_file(files_to_zip, output_zip_path):
    """
    Create a zip file from the provided files

    Args:
        files_to_zip (dict): Dictionary of {file_path: archive_name}
        output_zip_path (str): Path to save the zip file

    Returns:
        str: Path to the created zip file
    """
    # Verify source files exist
    for file_path in files_to_zip.keys():
        if not os.path.exists(file_path):
            logger.error(f"Source file not found: {file_path}")
            raise FileNotFoundError(f"Source file not found: {file_path}")
        if not os.path.isfile(file_path):
            logger.error(f"Source path is not a file: {file_path}")
            raise ValueError(f"Source path is not a file: {file_path}")

    # Ensure the parent directory exists
    os.makedirs(os.path.dirname(output_zip_path), exist_ok=True)

    logger.info(f"Creating zip file with {len(files_to_zip)} files at: {output_zip_path}")

    # Create the zip file
    with zipfile.ZipFile(output_zip_path, 'w') as zipf:
        for file_path, arc_name in files_to_zip.items():
            logger.debug(f"Adding to zip: {file_path} as {arc_name}")
            file_size = os.path.getsize(file_path)
            logger.debug(f"File size: {file_size} bytes")
            zipf.write(file_path, arcname=arc_name)

    # Verify the zip file was created
    if not os.path.exists(output_zip_path):
        logger.error(f"Failed to create zip file at {output_zip_path}")
        raise FileNotFoundError(f"Failed to create zip file at {output_zip_path}")

    zip_size = os.path.getsize(output_zip_path)
    logger.info(f"Created zip file: {output_zip_path}, size: {zip_size} bytes")

    return output_zip_path


def load_point_cloud_data(file_path):
    """
    Load point cloud data from a PLY file

    Args:
        file_path (str): Path to the PLY file

    Returns:
        tuple: (coords, colors, is_point_cloud)
    """
    logger.info(f"Loading point cloud data from: {file_path}")

    pcd_type = o3d.io.read_file_geometry_type(file_path)
    if pcd_type == o3d.io.FileGeometry.CONTAINS_TRIANGLES:
        logger.info(f"File contains triangles, loading as mesh")
        geometry = o3d.io.read_triangle_mesh(file_path)
        coords = np.array(geometry.vertices)
        colors = np.array(geometry.vertex_colors) if geometry.has_vertex_colors() else np.ones((len(coords), 3)) * 0.5
        is_point_cloud = False
        logger.info(f"Loaded mesh with {len(coords)} vertices")
    else:
        logger.info(f"File contains points, loading as point cloud")
        geometry = o3d.io.read_point_cloud(file_path)
        coords = np.array(geometry.points)
        colors = np.array(geometry.colors) if geometry.has_colors() else np.ones((len(coords), 3)) * 0.5
        is_point_cloud = True
        logger.info(f"Loaded point cloud with {len(coords)} points")

    return coords, colors, is_point_cloud


def get_obj_color(obj_id, normalize=True):
    """
    Generate a color for an object ID using HSL color space,
    matching the frontend's getColorFromIndex function.

    Args:
        obj_id (int): Object ID
        normalize (bool): Whether to normalize RGB values to 0-1 range
                         (normalize=True returns 0-1, normalize=False returns 0-255)

    Returns:
        list: [r, g, b] color values
    """
    # Use the same algorithm as the frontend's getColorFromIndex
    # In the frontend: const hue = (index * 50) % 360;
    hue = (obj_id * 50) % 360

    # Convert to 0-1 range for colorsys
    h = hue / 360

    # Use the same saturation and lightness as the frontend
    # In the frontend: saturation = 1.0, lightness = 0.5
    s = 1.0
    l = 0.5

    # Convert HSL to RGB (colorsys uses HSV, not HSL, so we need to convert)
    # This algorithm matches THREE.Color().setHSL() in JavaScript
    def hsl_to_rgb(h, s, l):
        # Convert HSL to RGB
        if l < 0.5:
            q = l * (1 + s)
        else:
            q = l + s - l * s
        p = 2 * l - q

        # Helper function
        def hue_to_rgb(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p

        r = hue_to_rgb(p, q, h + 1/3)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1/3)

        return r, g, b

    # Get RGB values
    r, g, b = hsl_to_rgb(h, s, l)

    # Return values based on normalization preference
    if normalize:
        # Already in 0-1 range
        return [r, g, b]
    else:
        # Convert to 0-255 range
        return [int(r * 255), int(g * 255), int(b * 255)]
