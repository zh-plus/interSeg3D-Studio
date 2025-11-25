"""
Rendering helper functions ported from legacy view_rendering module.
"""

import os
from pathlib import Path
from typing import List, Tuple, Union, Optional

import numpy as np
import open3d as o3d
from open3d.visualization import rendering

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


def load_geometry_from_file(
        file_path: str | Path,
        background_color: List[float],
) -> Tuple[str, np.ndarray, np.ndarray, Union[o3d.geometry.TriangleMesh, o3d.geometry.PointCloud]]:
    file_path = str(file_path)
    file_type = o3d.io.read_file_geometry_type(file_path)
    if file_type == o3d.io.FileGeometry.CONTAINS_TRIANGLES:
        geometry = o3d.io.read_triangle_mesh(file_path)
        coords = np.array(geometry.vertices)
        colors = (
            np.array(geometry.vertex_colors)
            if geometry.has_vertex_colors()
            else np.tile(background_color, (len(coords), 1))
        )
        geometry_type = "mesh"
        logger.debug("Loaded mesh geometry from file.")
    else:
        geometry = o3d.io.read_point_cloud(file_path)
        coords = np.array(geometry.points)
        colors = (
            np.array(geometry.colors)
            if geometry.has_colors()
            else np.tile(background_color, (len(coords), 1))
        )
        geometry_type = "pointcloud"
        logger.debug("Loaded point cloud geometry from file.")
    return geometry_type, coords, colors, geometry


def process_mask_mode(
        mask: np.ndarray,
        coords: np.ndarray,
        colors: np.ndarray,
        mask_mode: str,
        highlight_color: List[float]
) -> Tuple[np.ndarray, Optional[o3d.geometry.LineSet]]:
    updated_colors = colors.copy()
    outline = None
    if mask_mode == "full":
        updated_colors[mask] = highlight_color
    elif mask_mode == "outline":
        if not mask.any():
            raise ValueError("The mask did not select any points.")
        object_points = coords[mask]
        object_pcd = o3d.geometry.PointCloud()
        object_pcd.points = o3d.utility.Vector3dVector(object_points)
        hull, _ = object_pcd.compute_convex_hull()
        outline = o3d.geometry.LineSet.create_from_triangle_mesh(hull)
        outline.colors = o3d.utility.Vector3dVector(
            np.tile(highlight_color, (len(outline.lines), 1)))
    else:
        raise ValueError("mask_mode must be 'outline' or 'full'.")
    return updated_colors, outline


def create_vis_geometry(
        geometry_type: str,
        coords: np.ndarray,
        vis_colors: np.ndarray,
        original_geometry: Union[o3d.geometry.TriangleMesh, o3d.geometry.PointCloud]
) -> Union[o3d.geometry.TriangleMesh, o3d.geometry.PointCloud]:
    if geometry_type == "mesh":
        vis_geometry = o3d.geometry.TriangleMesh()
        vis_geometry.vertices = o3d.utility.Vector3dVector(coords)
        vis_geometry.vertex_colors = o3d.utility.Vector3dVector(vis_colors)
        vis_geometry.triangles = original_geometry.triangles
        vis_geometry.compute_vertex_normals()
    else:
        vis_geometry = o3d.geometry.PointCloud()
        vis_geometry.points = o3d.utility.Vector3dVector(coords)
        vis_geometry.colors = o3d.utility.Vector3dVector(vis_colors)
        vis_geometry.estimate_normals()
    return vis_geometry


def render_object_views(
        point_cloud_path: str,
        mask: Union[List[bool], np.ndarray],
        camera_pos: List[List[float]],
        output_dir: str = "./object_views",
        image_size: Tuple[int, int] = (1280, 720),
        highlight_color: List[float] = [1.0, 0.0, 0.0],
        background_color: List[float] = [0.8, 0.8, 0.8],
        view_angle: float = 60.0,
        mask_mode: str = "outline",
) -> List[str]:
    os.makedirs(output_dir, exist_ok=True)
    geometry_type, coords, colors, geometry = load_geometry_from_file(point_cloud_path, background_color)
    mask_bool = np.array(mask, dtype=bool)
    if mask_bool.shape[0] != len(coords):
        raise ValueError("Mask length does not match number of points in the geometry.")
    vis_colors, outline = process_mask_mode(mask_bool, coords, colors, mask_mode, highlight_color)
    vis_geometry = create_vis_geometry(geometry_type, coords, vis_colors, geometry)
    width, height = image_size
    renderer = rendering.OffscreenRenderer(width, height)
    bg_color = background_color + [1.0] if len(background_color) == 3 else background_color
    renderer.scene.set_background(bg_color)
    material = rendering.MaterialRecord()
    material.shader = "defaultUnlit"
    renderer.scene.add_geometry("geometry", vis_geometry, material)
    if mask_mode == "outline" and outline is not None:
        renderer.scene.add_geometry("outline", outline, material)
    near_plane = 0.1
    far_plane = 1000.0
    if not mask_bool.any():
        raise ValueError("The mask did not select any points.")
    object_center = np.mean(coords[mask_bool], axis=0)
    image_paths = []
    for idx, eye in enumerate(camera_pos):
        eye = np.array(eye)
        renderer.scene.camera.look_at(object_center, eye, np.array([0, 0, 1]))
        aspect = width / height
        renderer.scene.camera.set_projection(
            view_angle, aspect, near_plane, far_plane, rendering.Camera.FovType.Vertical
        )
        img = renderer.render_to_image()
        image_path = os.path.join(output_dir, f"view_{idx:03d}.png")
        o3d.io.write_image(image_path, img)
        image_paths.append(image_path)
        logger.debug(f"Saved view {idx} to {image_path}")
    return image_paths


def compute_object_center_and_radius(
        mask: np.ndarray, coords: np.ndarray
) -> Tuple[np.ndarray, float]:
    if not mask.any():
        raise ValueError("No masked points found in the geometry.")
    masked_coords = coords[mask]
    center = np.mean(masked_coords, axis=0)
    bounding_radius = np.max(np.linalg.norm(masked_coords - center, axis=1))
    return center, bounding_radius


def create_camera_markers(
        camera_positions: List[List[float]], bounding_radius: float
) -> o3d.geometry.PointCloud:
    camera_marker_clouds = []
    sphere_radius = bounding_radius * 0.1 if bounding_radius > 0 else 0.1
    for pos in camera_positions:
        sphere_mesh = o3d.geometry.TriangleMesh.create_sphere(radius=sphere_radius)
        sphere_mesh.translate(np.array(pos))
        sphere_mesh.paint_uniform_color([0.0, 0.999, 0.0])
        marker = sphere_mesh.sample_points_uniformly(number_of_points=500)
        camera_marker_clouds.append(marker)
    all_points = [np.asarray(cloud.points) for cloud in camera_marker_clouds]
    all_colors = [np.asarray(cloud.colors) for cloud in camera_marker_clouds]
    if all_points:
        all_points = np.vstack(all_points)
        all_colors = np.vstack(all_colors)
        camera_cloud = o3d.geometry.PointCloud()
        camera_cloud.points = o3d.utility.Vector3dVector(all_points)
        camera_cloud.colors = o3d.utility.Vector3dVector(all_colors)
    else:
        camera_cloud = o3d.geometry.PointCloud()
    return camera_cloud


def sample_line_points(line_set, num_samples=20):
    points = np.asarray(line_set.points)
    sampled_points = []
    for line in np.asarray(line_set.lines):
        start = points[line[0]]
        end = points[line[1]]
        for t in np.linspace(0, 1, num_samples):
            sample = start * (1 - t) + end * t
            sampled_points.append(sample)
    return np.array(sampled_points)


def test_camera_positions(
        point_cloud_path: str | Path,
        mask: Union[np.ndarray, str],
        output_dir: str = "./camera_test",
        view_angle: float = 60.0,
        distance_factor: float = 2.0,
        num_positions: int = 8,
        camera_height: Optional[float] = None,
        mask_mode: str = "outline",
        highlight_color: List[float] = [1.0, 0.0, 0.0],
        obj_id: int = 1
) -> List[str]:
    logger.info(f"Setting up camera positions...")
    point_cloud_path = Path(point_cloud_path)
    if isinstance(mask, str):
        if mask.endswith('.npy'):
            mask = np.load(mask)
        else:
            raise ValueError(f"Unsupported mask file format: {mask}")
    geometry_type, coords, colors, geometry = load_geometry_from_file(point_cloud_path, [0.5, 0.5, 0.5])
    mask_array = np.array(mask, dtype=int)
    obj_mask: np.ndarray[bool] = mask_array == obj_id
    if obj_mask.shape[0] != len(coords):
        raise ValueError("Mask length does not match number of points in the geometry.")
    vis_colors, outline = process_mask_mode(obj_mask, coords, colors.copy(), mask_mode, highlight_color)
    vis_geometry = create_vis_geometry(geometry_type, coords, vis_colors, geometry)
    center, bounding_radius = compute_object_center_and_radius(obj_mask, coords)
    if camera_height is None:
        camera_height = np.min(coords[:, 2]) + 1.5
    camera_positions = []
    radius = bounding_radius * distance_factor
    for i in range(num_positions):
        angle = 2 * np.pi * i / num_positions
        x = center[0] + radius * np.cos(angle)
        y = center[1] + radius * np.sin(angle)
        camera_positions.append([x, y, camera_height])
    camera_cloud = create_camera_markers(camera_positions, bounding_radius)
    if geometry_type == "mesh":
        scene_cloud = o3d.geometry.PointCloud()
        scene_cloud.points = o3d.utility.Vector3dVector(np.asarray(vis_geometry.vertices))
        scene_cloud.colors = o3d.utility.Vector3dVector(np.asarray(vis_geometry.vertex_colors))
    else:
        scene_cloud = vis_geometry
    if mask_mode == "outline" and outline is not None:
        sampled_outline_points = sample_line_points(outline, num_samples=20)
        outline_colors = np.tile(np.array(highlight_color), (len(sampled_outline_points), 1))
        outline_cloud = o3d.geometry.PointCloud()
        outline_cloud.points = o3d.utility.Vector3dVector(sampled_outline_points)
        outline_cloud.colors = o3d.utility.Vector3dVector(outline_colors)
        combined_points = np.vstack((np.asarray(scene_cloud.points), np.asarray(outline_cloud.points)))
        combined_colors = np.vstack((np.asarray(scene_cloud.colors), np.asarray(outline_cloud.colors)))
        scene_cloud.points = o3d.utility.Vector3dVector(combined_points)
        scene_cloud.colors = o3d.utility.Vector3dVector(combined_colors)
    combined_points = np.vstack((np.asarray(scene_cloud.points), np.asarray(camera_cloud.points)))
    combined_colors = np.vstack((np.asarray(scene_cloud.colors), np.asarray(camera_cloud.colors)))
    combined_scene = o3d.geometry.PointCloud()
    combined_scene.points = o3d.utility.Vector3dVector(combined_points)
    combined_scene.colors = o3d.utility.Vector3dVector(combined_colors)
    os.makedirs(output_dir, exist_ok=True)
    ply_output_path = os.path.join(output_dir, "scene_with_camera_markers.ply")
    logger.info("Writing scene PLY with camera markers...")
    o3d.io.write_point_cloud(ply_output_path, combined_scene)
    logger.info(f"Scene PLY with camera markers saved to {ply_output_path}")
    return render_object_views(
        point_cloud_path=str(point_cloud_path),
        mask=obj_mask,
        camera_pos=camera_positions,
        output_dir=output_dir,
        view_angle=view_angle,
        mask_mode=mask_mode,
    )


