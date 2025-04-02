# ------------------------------------------------------------------------
# Inference script for interactive segmentation
# ------------------------------------------------------------------------
import sys

sys.path.insert(0, './agile3d')

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union

import MinkowskiEngine as ME
import numpy as np
import open3d as o3d
import torch

from interactive_tool.utils import get_obj_color
from models import build_model


@dataclass
class Click:
    """A class to represent a user click in 3D space with relevant metadata."""
    position: torch.Tensor  # 3D coordinates of the click (torch.Tensor)
    obj_idx: int  # Object index this click belongs to (0 for background)
    obj_name: str  # Object name this click belongs to
    time_idx: int  # Temporal index of the click (order in the sequence)
    is_positive: bool = True  # Whether this is a positive or negative click
    id: Optional[int] = None  # Index in the point cloud (set during processing)
    cube_size: float = 0.02  # Size of the selection cube around the click

    def find_nearest_point(self, coords: torch.Tensor) -> int:
        """Find the nearest point in the point cloud to this click."""
        # Make sure position is on the same device as coords
        position = self.position.to(coords.device)

        # Calculate distances from click position to all points
        distance = torch.cdist(coords, position.unsqueeze(0), p=2)
        nearest_idx = distance.argmin().item()
        self.id = int(nearest_idx)
        return nearest_idx

    def get_cube_mask(self, coords: Union[np.ndarray, torch.Tensor]) -> np.ndarray:
        """Get a mask for points within a cube of size cube_size around the click position."""
        # Convert coords to numpy if it's a tensor
        if isinstance(coords, torch.Tensor):
            coords_np = coords.detach().cpu().numpy()
        else:
            coords_np = coords

        # Convert position to numpy for consistent comparison
        position_np = self.position.detach().cpu().numpy()

        mask = np.zeros(coords_np.shape[0], dtype=bool)
        mask[np.logical_and(np.logical_and(
            (np.absolute(coords_np[:, 0] - position_np[0]) < self.cube_size),
            (np.absolute(coords_np[:, 1] - position_np[1]) < self.cube_size)),
            (np.absolute(coords_np[:, 2] - position_np[2]) < self.cube_size))] = True
        return mask

    def to_dict(self) -> dict:
        """Convert to a dictionary for JSON serialization."""
        return {
            'position': self.position.detach().cpu().numpy().tolist(),
            'obj_idx': int(self.obj_idx),
            'obj_name': self.obj_name,
            'time_idx': int(self.time_idx),
            'is_positive': bool(self.is_positive),
            'id': int(self.id) if self.id is not None else None,
            'cube_size': float(self.cube_size)
        }


class ClickHandler:
    """Manages a collection of clicks and provides utilities for processing them."""

    def __init__(self):
        self.clicks: List[Click] = []
        self.next_time_idx = 0
        self.click_idx = {'0': []}  # Format used by the model
        self.click_time_idx = {'0': []}  # Format used by the model
        self.click_positions = {'0': []}  # Additional storage for positions

    def add_click(self, position: Union[np.ndarray, torch.Tensor, List[float]], obj_idx: int, obj_name: str,
                  is_positive: bool = True, cube_size: float = 0.02) -> Click:
        """Add a new click and return it."""
        # Convert position to torch.Tensor if it's not already
        if isinstance(position, np.ndarray):
            position = torch.tensor(position, dtype=torch.float32)
        elif isinstance(position, list):
            position = torch.tensor(position, dtype=torch.float32)

        click = Click(
            position=position,
            obj_idx=obj_idx,
            obj_name=obj_name,
            time_idx=self.next_time_idx,
            is_positive=is_positive,
            cube_size=cube_size
        )
        self.clicks.append(click)
        self.next_time_idx += 1
        return click

    def add_clicks_from_file(self, filepath: str, coords: torch.Tensor) -> None:
        """Load clicks from a JSON file and add them to the handler."""
        with open(filepath, 'r') as f:
            click_data = json.load(f)

        for click_info in click_data:
            position = torch.tensor(click_info['position'], dtype=torch.float32)
            click = Click(
                position=position,
                obj_idx=click_info['obj_idx'],
                obj_name=click_info['obj_name'],
                time_idx=click_info['time_idx'] if 'time_idx' in click_info else self.next_time_idx,
                is_positive=click_info.get('is_positive', True),
                cube_size=click_info.get('cube_size', 0.02)
            )
            click.find_nearest_point(coords)
            self.clicks.append(click)
            self.next_time_idx = max(self.next_time_idx, click.time_idx + 1)

            # Update model-compatible formats
            self._update_click_dicts(click)

    def save_clicks_to_file(self, filepath: str) -> None:
        """Save all clicks to a JSON file."""
        click_data = []
        for click in self.clicks:
            click_data.append(click.to_dict())

        with open(filepath, 'w') as f:
            json.dump(click_data, f, indent=2)

    def process_clicks(self, coords: torch.Tensor) -> None:
        """Find nearest points in the point cloud for all clicks."""
        self.click_idx = {'0': []}
        self.click_time_idx = {'0': []}
        self.click_positions = {'0': []}

        for click in self.clicks:
            click.find_nearest_point(coords)
            self._update_click_dicts(click)

    def _update_click_dicts(self, click: Click) -> None:
        """Update the dictionaries used by the model with a click."""
        if click.id is None:
            return

        obj_key = str(click.obj_idx)
        if obj_key not in self.click_idx:
            self.click_idx[obj_key] = []
            self.click_time_idx[obj_key] = []
            self.click_positions[obj_key] = []

        self.click_idx[obj_key].append(click.id)
        self.click_time_idx[obj_key].append(click.time_idx)
        self.click_positions[obj_key].append(click.position.detach().cpu().numpy().tolist())

    def get_click_data_for_model(self) -> Tuple[
        Dict[str, List[int]], Dict[str, List[int]], Dict[str, List[List[float]]]]:
        """Get the click data in the format expected by the model."""
        return self.click_idx, self.click_time_idx, self.click_positions

    def get_all_click_masks(self, coords: torch.Tensor) -> Dict[int, np.ndarray]:
        """Get masks for all objects based on clicks."""
        masks = {}
        for click in self.clicks:
            if click.obj_idx not in masks:
                masks[click.obj_idx] = np.zeros(coords.shape[0], dtype=bool)

            # Add cube region to object mask
            cube_mask = click.get_cube_mask(coords)
            masks[click.obj_idx] = np.logical_or(masks[click.obj_idx], cube_mask)

        return masks


class PointCloudInference:
    """Handles inference on a point cloud using a pre-trained model and user clicks."""

    def __init__(self, pretraining_weights='agile3d/weights/checkpoint1099.pth', voxel_size=0.05):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # Set default model parameters
        self.config = type('config', (), {
            # Model parameters
            'pretraining_weights': pretraining_weights,
            'voxel_size': voxel_size,

            # Backbone parameters
            'dialations': [1, 1, 1, 1],
            'conv1_kernel_size': 5,
            'bn_momentum': 0.02,

            # Transformer parameters
            'hidden_dim': 128,
            'dim_feedforward': 1024,
            'num_heads': 8,
            'num_decoders': 3,
            'num_bg_queries': 10,
            'dropout': 0.0,
            'pre_norm': False,
            'normalize_pos_enc': True,
            'positional_encoding_type': "fourier",
            'gauss_scale': 1.0,
            'hlevels': [4],
            'shared_decoder': False,
            'aux': True
        })

        # Load model
        self.model = build_model(self.config)
        self.model.to(self.device)
        self.model.eval()

        if pretraining_weights:
            map_location = None if torch.cuda.is_available() else 'cpu'
            model_dict = torch.load(pretraining_weights, map_location=map_location)
            missing_keys, unexpected_keys = self.model.load_state_dict(model_dict['model'], strict=False)

            unexpected_keys = [k for k in unexpected_keys if
                               not (k.endswith('total_params') or k.endswith('total_ops'))]
            if len(missing_keys) > 0:
                print('Missing Keys: {}'.format(missing_keys))
            if len(unexpected_keys) > 0:
                print('Unexpected Keys: {}'.format(unexpected_keys))

        print(f"Model loaded from {pretraining_weights}")
        self.quantization_size = voxel_size

        # Initialize data structures
        self.point_cloud = None
        self.coords = None
        self.colors = None
        self.click_handler = ClickHandler()

        # Model inference variables
        self.pcd_features = None
        self.aux = None
        self.coordinates = None
        self.pos_encodings_pcd = None
        self.inverse_map = None
        self.unique_map = None
        self.raw_coords_qv = None

    def load_point_cloud(self, filepath: Union[str, Path]) -> None:
        """Load a point cloud from a PLY file."""
        print(f"Loading point cloud from {filepath}")
        self.last_loaded_file = filepath

        # Convert Path to string if needed
        if isinstance(filepath, Path):
            filepath = str(filepath)

        # Check file exists
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Point cloud file not found: {filepath}")

        # Determine geometry type
        pcd_type = o3d.io.read_file_geometry_type(filepath)

        if pcd_type == o3d.io.FileGeometry.CONTAINS_TRIANGLES:
            mesh = o3d.io.read_triangle_mesh(filepath)
            self.point_cloud = mesh
            self.coords = np.array(mesh.vertices)
            self.colors = np.array(mesh.vertex_colors) if mesh.has_vertex_colors() else np.ones(
                (len(mesh.vertices), 3)) * 0.5
            self.point_type = "mesh"
            print(f"Loaded mesh with {len(mesh.vertices)} vertices")
        elif pcd_type == o3d.io.FileGeometry.CONTAINS_POINTS:
            pcd = o3d.io.read_point_cloud(filepath)
            self.point_cloud = pcd
            self.coords = np.array(pcd.points)
            self.colors = np.array(pcd.colors) if pcd.has_colors() else np.ones((len(pcd.points), 3)) * 0.5
            self.point_type = "pointcloud"
            print(f"Loaded point cloud with {len(pcd.points)} points")
        else:
            raise ValueError(f"Unknown point cloud format in {filepath}")

        # Reset click handler for new point cloud
        self.click_handler = ClickHandler()

        # Preprocess for model inference
        self._preprocess_point_cloud()

    def _preprocess_point_cloud(self) -> None:
        """Prepare the point cloud for model inference."""
        # Sparse quantization as in original code
        coords_qv, unique_map, inverse_map = ME.utils.sparse_quantize(
            coordinates=self.coords,
            quantization_size=self.quantization_size,
            return_index=True,
            return_inverse=True
        )

        self.coords_qv = coords_qv
        self.unique_map = unique_map
        self.inverse_map = inverse_map.to(self.device)
        self.colors_qv = torch.from_numpy(self.colors[unique_map]).float()
        self.raw_coords_qv = torch.from_numpy(self.coords[unique_map]).float().to(self.device)

        # Compute backbone features
        data = ME.SparseTensor(
            coordinates=ME.utils.batched_coordinates([self.coords_qv]),
            features=self.colors_qv,
            device=self.device
        )

        self.pcd_features, self.aux, self.coordinates, self.pos_encodings_pcd = self.model.forward_backbone(
            data, raw_coordinates=self.raw_coords_qv
        )

        print(f"Processed point cloud features: {self.pcd_features.F.shape}")

    def load_clicks(self, filepath: str) -> None:
        """Load clicks from a file."""
        # Use raw_coords_qv for nearest point calculation
        self.click_handler.add_clicks_from_file(filepath, self.raw_coords_qv)
        print(f"Loaded {len(self.click_handler.clicks)} clicks from {filepath}")

    def add_click(self, position: Union[np.ndarray, List[float], torch.Tensor], obj_idx: int, obj_name: str,
                  is_positive: bool = True, cube_size: float = 0.02) -> Click:
        """Add a new click and process it."""
        click = self.click_handler.add_click(position, obj_idx, obj_name, is_positive, cube_size)
        # Use raw_coords_qv for nearest point calculation
        click.find_nearest_point(self.raw_coords_qv)
        return click

    def run_inference(self) -> np.ndarray:
        """Run model inference with the current clicks."""
        if self.coords is None or self.pcd_features is None:
            raise ValueError("Point cloud not loaded or processed. Call load_point_cloud first.")

        if not self.click_handler.clicks:
            raise ValueError("No clicks available. Add clicks before running inference.")

        # Process all clicks to find their nearest points using raw_coords_qv
        self.click_handler.process_clicks(self.raw_coords_qv)

        # Get click data in the format required by the model
        click_idx, click_time_idx, click_positions = self.click_handler.get_click_data_for_model()

        # Run model inference
        outputs = self.model.forward_mask(
            self.pcd_features,
            self.aux,
            self.coordinates,
            self.pos_encodings_pcd,
            click_idx=[click_idx],
            click_time_idx=[click_time_idx]
        )

        # Process predictions
        pred = outputs['pred_masks'][0].argmax(1)

        # Ensure click points match their object labels
        for obj_id, cids in click_idx.items():
            if obj_id != '0':  # Skip background class
                pred[cids] = int(obj_id)

        # Apply cube area masks for each click (similar to the GUI behavior)
        click_masks = self.click_handler.get_all_click_masks(self.raw_coords_qv)
        for obj_idx, mask in click_masks.items():
            if obj_idx != 0:  # Skip background
                pred[mask] = obj_idx

        # Map back to original point cloud
        pred_full = pred[self.inverse_map]
        mask = pred_full.cpu().numpy()

        # Save prediction data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        scene_name = os.path.basename(os.path.splitext(str(self.last_loaded_file))[0]) if hasattr(self,
                                                                                                  'last_loaded_file') else "unknown"
        num_obj = len(click_idx.keys()) - 1
        num_click = sum([len(c) for c in click_idx.values()])
        avg_clicks = round(num_click / max(num_obj, 1), 1)

        print(f"Inference complete. Found {len(np.unique(mask)) - 1} objects with {num_click} clicks")
        return mask

    def visualize_results(self, mask: np.ndarray) -> None:
        """Visualize the segmentation results."""
        colors = self.colors.copy()

        # Color each object with a unique color
        obj_ids = np.unique(mask)
        obj_ids = [obj_id for obj_id in obj_ids if obj_id != 0]
        for obj_id in obj_ids:
            obj_mask = mask == obj_id
            colors[obj_mask] = get_obj_color(obj_id, normalize=True)

        # Mark click points with larger points for better visibility
        for click in self.click_handler.clicks:
            if click.id is not None:
                # For visualization, use full point cloud coordinates
                coords_tensor = torch.from_numpy(self.coords).float()
                cube_mask = click.get_cube_mask(coords_tensor)
                if click.obj_idx == 0:  # Background click
                    colors[cube_mask] = [0.1, 0.1, 0.1]  # Dark color for background
                else:
                    # Use a brighter version of the object color
                    obj_color = get_obj_color(click.obj_idx, normalize=True)
                    bright_color = np.minimum(1.0, np.array(obj_color) * 1.5)
                    colors[cube_mask] = bright_color

        # Create a new point cloud for visualization
        vis_pcd = o3d.geometry.PointCloud()
        vis_pcd.points = o3d.utility.Vector3dVector(self.coords)
        vis_pcd.colors = o3d.utility.Vector3dVector(colors)

        if self.point_type == "pointcloud":
            # Estimate normals for better visualization
            vis_pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.005, max_nn=30))

        # Visualize
        o3d.visualization.draw_geometries([vis_pcd])

    def save_results(self, mask: np.ndarray, output_dir: str, prefix: str = "") -> str:
        """Save the segmentation results (colored mesh)."""
        os.makedirs(output_dir, exist_ok=True)

        # Get scene name from file if available
        scene_name = os.path.basename(os.path.splitext(str(self.last_loaded_file))[0]) if hasattr(self,
                                                                                                  'last_loaded_file') else "unknown"
        if not prefix:
            prefix = scene_name

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_mask_{timestamp}.npy"
        mask_path = os.path.join(output_dir, filename)

        np.save(mask_path, mask)
        print(f"Saved mask to {mask_path}")

        # Create record file (similar to the format in the original code)
        record_file = os.path.join(output_dir, f"{prefix}_record.csv")
        with open(record_file, 'a') as f:
            now = datetime.now()
            num_obj = len(self.click_handler.click_idx.keys()) - 1
            num_click = sum([len(c) for c in self.click_handler.click_idx.values()])
            avg_clicks = round(num_click / max(num_obj, 1), 1)

            # Calculate mean IoU if ground truth is available (optional)
            sample_iou = 'NA'  # Placeholder for IoU if no ground truth available

            line = now.strftime("%Y-%m-%d-%H-%M-%S") + '  ' + scene_name + '  NumObjects:' + str(
                num_obj) + '  AvgNumClicks:' + str(avg_clicks) + '  mIoU:' + sample_iou + '\n'
            f.write(line)
            print(line)

        # Save clicks as well
        clicks_file = os.path.join(output_dir, f"{prefix}_clicks_{timestamp}.json")
        self.click_handler.save_clicks_to_file(clicks_file)
        print(f"Saved clicks to {clicks_file}")

        # Save colored point cloud
        colors = self.colors.copy()
        obj_ids = np.unique(mask)
        for obj_id in obj_ids:
            if obj_id != 0:  # Skip background
                obj_mask = mask == obj_id
                colors[obj_mask] = get_obj_color(obj_id, normalize=True)

        # Create colored point cloud for saving
        if self.point_type == "pointcloud":
            vis_pcd = o3d.geometry.PointCloud()
            vis_pcd.points = o3d.utility.Vector3dVector(self.coords)
            vis_pcd.colors = o3d.utility.Vector3dVector(colors)
            colored_ply_file = os.path.join(output_dir, f"{prefix}_result_{timestamp}.ply")
            o3d.io.write_point_cloud(colored_ply_file, vis_pcd)
        else:  # Mesh
            vis_mesh = o3d.geometry.TriangleMesh()
            vis_mesh.vertices = o3d.utility.Vector3dVector(self.coords)
            vis_mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
            # We would need to set the triangles as well but we don't have them from loading
            # This is a simplified version
            colored_ply_file = os.path.join(output_dir, f"{prefix}_result_{timestamp}.ply")
            o3d.io.write_triangle_mesh(colored_ply_file, vis_mesh)

        print(f"Saved colored {self.point_type} to {colored_ply_file}")

        return colored_ply_file


def infer(
        point_cloud_path: Union[str, Path],
        clicks_file=None,
        output_dir="./outputs",
        visualize=False,
        click_positions=None,
        click_obj_indices=None,
        click_obj_names=None,
        cube_size=0.02,
        pretraining_weights='agile3d/weights/checkpoint1099.pth',
        voxel_size=0.05
):
    """
    Run inference on a point cloud with user clicks.

    Args:
        point_cloud_path (Union[str, Path]): Path to input point cloud PLY file
        clicks_file (str, optional): Path to JSON file containing click information
        output_dir (str): Directory to save output files
        visualize (bool): Whether to visualize results after inference
        click_positions (list): List of click positions as np.arrays or lists
        click_obj_indices (list): List of object indices for each click (0 for background)
        click_obj_names (list): List of object names for each click
        cube_size (float): Size of the cube area around each click
        pretraining_weights (str): Path to model weights
        voxel_size (float): Voxel size for point cloud quantization

    Returns:
        str: Path to the saved colored ply file
        np.ndarray: The segmentation mask
    """
    # Initialize inference
    print(f"Using device: {torch.device('cuda' if torch.cuda.is_available() else 'cpu')}")
    inference = PointCloudInference(
        pretraining_weights=pretraining_weights,
        voxel_size=voxel_size
    )

    # Load point cloud
    inference.load_point_cloud(point_cloud_path)

    # Load clicks from file if provided
    if clicks_file:
        inference.load_clicks(clicks_file)

    # Or add clicks manually if provided through arguments
    elif click_positions and click_obj_indices:
        if len(click_positions) != len(click_obj_indices):
            raise ValueError("Number of click positions and object indices must match")

        # Generate default object names if not provided
        if not click_obj_names:
            click_obj_names = []
            for idx in click_obj_indices:
                if idx == 0:
                    click_obj_names.append("background")
                else:
                    click_obj_names.append(f"object_{idx}")
        elif len(click_positions) != len(click_obj_names):
            raise ValueError("If provided, number of object names must match click positions")

        for pos, obj_idx, obj_name in zip(click_positions, click_obj_indices, click_obj_names):
            inference.add_click(pos, obj_idx, obj_name, cube_size=cube_size)

    # Run inference if we have clicks
    if inference.click_handler.clicks:
        mask = inference.run_inference()
        result_path = inference.save_results(mask, output_dir)

        if visualize:
            inference.visualize_results(mask)

        return result_path, mask
    else:
        print("No clicks provided. Please provide clicks via clicks_file or click_positions.")
        return None, None


# Example usage:
if __name__ == '__main__':
    pcd_path = Path('data/interactive_dataset/scene_00_reconstructed_01_transformed_mesh/scan.ply')

    # # Example 1: Using a clicks file
    # result_path, mask = infer(
    #     point_cloud_path=pcd_path,
    #     clicks_file="path/to/clicks.json",
    #     visualize=True
    # )
    # print(result_path)

    # Example 2: Manually specifying clicks
    result_path, mask = infer(
        point_cloud_path=pcd_path,
        click_positions=[[1.3158004, 1.5544679, 0.4713757], [-0.14292482, 1.3323758, 0.49515364]],
        click_obj_indices=[1, 2],
        click_obj_names=["sofa", "desk"],
        output_dir="./output"
    )
    print(result_path)
