import json
import os
import zipfile

import numpy as np
import open3d as o3d

from infrastructure.logging.logger import get_logger

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
        if hasattr(obj, 'item'):
            return obj.item()
        return super().default(obj)


def create_colored_ply(coords, colors, mask, is_point_cloud, original_geometry_path, output_path, get_obj_color_func):
    new_colors = np.ones((len(coords), 3)) * 0.7
    unique_obj_ids = np.unique(mask)
    logger.info(f"Coloring {len(unique_obj_ids)} unique object IDs")
    for obj_id in unique_obj_ids:
        if obj_id > 0:
            obj_mask = mask == obj_id
            obj_color = get_obj_color_func(obj_id, normalize=True)
            new_colors[obj_mask] = obj_color
            logger.info(f"Applied color to object {obj_id}: {np.sum(obj_mask)} points")
    if not is_point_cloud:
        logger.info(f"Processing as mesh: {original_geometry_path}")
        original_mesh = o3d.io.read_triangle_mesh(original_geometry_path)
        new_geometry = o3d.geometry.TriangleMesh()
        new_geometry.vertices = o3d.utility.Vector3dVector(coords)
        new_geometry.vertex_colors = o3d.utility.Vector3dVector(new_colors)
        new_geometry.triangles = original_mesh.triangles
        new_geometry.compute_vertex_normals()
        o3d.io.write_triangle_mesh(output_path, new_geometry)
    else:
        logger.info(f"Processing as point cloud: {original_geometry_path}")
        new_geometry = o3d.geometry.PointCloud()
        new_geometry.points = o3d.utility.Vector3dVector(coords)
        new_geometry.colors = o3d.utility.Vector3dVector(new_colors)
        o3d.io.write_point_cloud(output_path, new_geometry)
    logger.info(f"Created colored geometry file: {output_path}")
    return output_path


def generate_metadata_json(mask, new_ply_path, original_file_path, object_info, inference_obj, get_obj_color_func):
    logger.info("Generating metadata JSON")
    metadata = {
        "objects": [],
        "file_info": {
            "ply_file": os.path.basename(new_ply_path),
            "original_file": os.path.basename(original_file_path)
        }
    }
    if object_info:
        logger.info(f"Adding object info from recognition results: {len(object_info)} objects")
        for obj_info in object_info:
            obj_id = None
            if 'obj_id' in obj_info:
                obj_id = obj_info['obj_id']
            else:
                label = obj_info.get('label', '')
                import re
                match = re.search(r'\d+', label)
                if match:
                    obj_id = int(match.group())
            if obj_id is None:
                obj_id = len(metadata["objects"]) + 1
            obj_color = get_obj_color_func(obj_id, normalize=True)
            if hasattr(obj_color, 'tolist'):
                obj_color = obj_color.tolist()
            if obj_info.get("type") == 'point':
                obj_data = {
                    "id": int(obj_id),
                    "label": obj_info.get("label", f"Object {obj_id}"),
                    "position": obj_info.get("position"),
                    "description": obj_info.get("description", ""),
                }
                if 'point' not in metadata:
                    metadata['point'] = []
                metadata['point'].append(obj_data)
            else:
                obj_data = {
                    "id": int(obj_id),
                    "label": obj_info.get("label", f"Object {obj_id}"),
                    "description": obj_info.get("description", ""),
                    "color": obj_color
                }
                if "cost" in obj_info and obj_info["cost"]:
                    obj_data["cost"] = float(obj_info["cost"])
                metadata["objects"].append(obj_data)
            logger.info(f"Added object {obj_id} to metadata")
    else:
        logger.info("No object info available, creating basic metadata from mask")
        unique_obj_ids = np.unique(mask)
        for obj_id in unique_obj_ids:
            if obj_id > 0:
                obj_color = get_obj_color_func(obj_id, normalize=True)
                if hasattr(obj_color, 'tolist'):
                    obj_color = obj_color.tolist()
                metadata["objects"].append({
                    "id": int(obj_id),
                    "label": f"Object {obj_id}",
                    "color": obj_color
                })
                logger.info(f"Added basic object {obj_id} to metadata")
    if inference_obj and inference_obj.click_handler:
        logger.info("Adding click data to metadata")
        click_data = []
        for click in inference_obj.click_handler.clicks:
            click_dict = {}
            raw_dict = click.to_dict()
            for k, v in raw_dict.items():
                if hasattr(v, 'tolist'):
                    click_dict[k] = v.tolist()
                elif hasattr(v, 'item'):
                    click_dict[k] = v.item()
                else:
                    click_dict[k] = v
            click_data.append(click_dict)
        metadata["click_data"] = click_data
        logger.info(f"Added {len(click_data)} clicks to metadata")
    unique_values, counts = np.unique(mask, return_counts=True)
    object_counts = {}
    for i, val in enumerate(unique_values):
        if val > 0:
            object_counts[int(val)] = int(counts[i])
    metadata["object_counts"] = object_counts
    logger.info(f"Added point counts for {len(object_counts)} objects to metadata")
    return metadata


def create_zip_file(files_to_zip, output_zip_path):
    for file_path in files_to_zip.keys():
        if not os.path.exists(file_path):
            logger.error(f"Source file not found: {file_path}")
            raise FileNotFoundError(f"Source file not found: {file_path}")
        if not os.path.isfile(file_path):
            logger.error(f"Source path is not a file: {file_path}")
            raise ValueError(f"Source path is not a file: {file_path}")
    os.makedirs(os.path.dirname(output_zip_path), exist_ok=True)
    logger.info(f"Creating zip file with {len(files_to_zip)} files at: {output_zip_path}")
    with zipfile.ZipFile(output_zip_path, 'w') as zipf:
        for file_path, arc_name in files_to_zip.items():
            logger.debug(f"Adding to zip: {file_path} as {arc_name}")
            file_size = os.path.getsize(file_path)
            logger.debug(f"File size: {file_size} bytes")
            zipf.write(file_path, arcname=arc_name)
    if not os.path.exists(output_zip_path):
        logger.error(f"Failed to create zip file at {output_zip_path}")
        raise FileNotFoundError(f"Failed to create zip file at {output_zip_path}")
    zip_size = os.path.getsize(output_zip_path)
    logger.info(f"Created zip file: {output_zip_path}, size: {zip_size} bytes")
    return output_zip_path


def get_obj_color(obj_id, normalize=True):
    hue = (obj_id * 50) % 360
    h = hue / 360
    s = 1.0
    l = 0.5
    def hsl_to_rgb(h, s, l):
        if l < 0.5:
            q = l * (1 + s)
        else:
            q = l + s - l * s
        p = 2 * l - q
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
    r, g, b = hsl_to_rgb(h, s, l)
    if normalize:
        return [r, g, b]
    else:
        return [int(r * 255), int(g * 255), int(b * 255)]


