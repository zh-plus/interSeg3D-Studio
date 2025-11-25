from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union

import MinkowskiEngine as ME
import numpy as np
import open3d as o3d
import torch

from pinpoint3d.models import build_PinPoint3D
from infrastructure.logging.logger import get_logger, StepTimer, timed
from core.utils.app_utils import get_obj_color

logger = get_logger("inference")


@dataclass
class Click:
    position: torch.Tensor
    obj_idx: int
    obj_name: str
    time_idx: int
    part_idx: int
    is_positive: bool = True
    id: Optional[int] = None
    cube_size: float = 0.02

    def find_nearest_point(self, coords: torch.Tensor) -> int:
        position = self.position.to(coords.device)
        distance = torch.cdist(coords, position.unsqueeze(0), p=2)
        nearest_idx = distance.argmin().item()
        self.id = int(nearest_idx)
        return nearest_idx

    def get_cube_mask(self, coords: Union[np.ndarray, torch.Tensor]) -> np.ndarray:
        if isinstance(coords, torch.Tensor):
            coords_np = coords.detach().cpu().numpy()
        else:
            coords_np = coords
        position_np = self.position.detach().cpu().numpy()
        mask = np.zeros(coords_np.shape[0], dtype=bool)
        mask[np.logical_and(np.logical_and(
            (np.absolute(coords_np[:, 0] - position_np[0]) < self.cube_size),
            (np.absolute(coords_np[:, 1] - position_np[1]) < self.cube_size)),
            (np.absolute(coords_np[:, 2] - position_np[2]) < self.cube_size))] = True
        return mask

    def to_dict(self) -> dict:
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
    def __init__(self):
        self.clicks: List[Click] = []
        self.next_time_idx = 0
        # self.click_idx = {'0': []}
        # self.click_time_idx = {'0': []}
        # self.click_positions = {'0': []}
        self.click_idx: Dict[str, Dict[str, List[int]]] = {}
        self.click_time_idx: Dict[str, Dict[str, List[int]]] = {}
        self.click_positions: Dict[str, Dict[str, List[List[float]]]] = {}

    def add_click(self, position: Union[np.ndarray, torch.Tensor, List[float]], obj_idx: int, obj_name: str,
                  is_positive: bool = True, cube_size: float = 0.02) -> Click:
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
        logger.debug(f"Added click for object {obj_idx} ({obj_name}) at position {position.tolist()}")
        return click

    def add_clicks_from_file(self, filepath: str, coords: torch.Tensor) -> None:
        import json
        logger.info(f"Loading clicks from file: {filepath}")
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
            self._update_click_dicts(click)
        logger.info(f"Loaded {len(self.clicks)} clicks from file")

    def save_clicks_to_file(self, filepath: str) -> None:
        import json
        logger.info(f"Saving {len(self.clicks)} clicks to file: {filepath}")
        click_data = [click.to_dict() for click in self.clicks]
        with open(filepath, 'w') as f:
            json.dump(click_data, f, indent=2)
        logger.info(f"Clicks saved to: {filepath}")

    def process_clicks(self, coords: torch.Tensor) -> None:
        logger.info(f"Processing {len(self.clicks)} clicks")
        self.click_idx = {'0': []}
        self.click_time_idx = {'0': []}
        self.click_positions = {'0': []}
        for click in self.clicks:
            click.find_nearest_point(coords)
            self._update_click_dicts(click)

    # def _update_click_dicts(self, click: Click) -> None:
    #     if click.id is None:
    #         logger.warning(f"Click has no ID, skipping dictionary update")
    #         return
    #     obj_key = str(click.obj_idx)
    #     if obj_key not in self.click_idx:
    #         self.click_idx[obj_key] = []
    #         self.click_time_idx[obj_key] = []
    #         self.click_positions[obj_key] = []
    #     self.click_idx[obj_key].append(click.id)
    #     self.click_time_idx[obj_key].append(click.time_idx)
    #     self.click_positions[obj_key].append(click.position.detach().cpu().numpy().tolist())
    #     logger.debug(f"Updated click dictionaries for object {obj_key}, click ID {click.id}")

    def _update_click_dicts(self, click: Click) -> None:
        """Update the dictionaries used by the model with a click."""
        if click.id is None:
            logger.warning(f"Click has no ID, skipping dictionary update")
            return

        part_key = str(click.part_idx)
        obj_key = str(click.obj_idx)
        if obj_key == '0':
            if obj_key not in self.click_idx:
                self.click_idx[obj_key] = []
                self.click_time_idx[obj_key] = []
                self.click_positions[obj_key] = []

            self.click_idx[obj_key].append(click.id)
            self.click_time_idx[obj_key].append(click.time_idx)
            self.click_positions[obj_key].append(click.position.detach().cpu().numpy().tolist())
            logger.debug(f"Updated click dictionaries for object {obj_key}, click ID {click.id}")
        else:
            # 一级：obj
            if obj_key not in self.click_idx:
                self.click_idx[obj_key] = {}
                self.click_time_idx[obj_key] = {}
                self.click_positions[obj_key] = {}
            # 二级：part
            if part_key not in self.click_idx[obj_key]:
                self.click_idx[obj_key][part_key] = []
                self.click_time_idx[obj_key][part_key] = []
                self.click_positions[obj_key][part_key] = []
            # 追加
            self.click_idx[obj_key][part_key].append(click.id)
            self.click_time_idx[obj_key][part_key].append(click.time_idx)
            self.click_positions[obj_key][part_key].append(
                click.position.detach().cpu().numpy().tolist()
            )

        logger.debug(
            f"Updated click dicts for obj {obj_key}, part {part_key}, click ID {click.id}"
        )

    def get_click_data_for_model(self) -> Tuple[
        Dict[str, List[int]], Dict[str, List[int]], Dict[str, List[List[float]]]]:
        logger.debug(f"Getting click data for model: {sum(len(v) for v in self.click_idx.values())} total clicks")
        return self.click_idx, self.click_time_idx, self.click_positions

    # def get_all_click_masks(self, coords: torch.Tensor) -> Dict[int, np.ndarray]:
    #     masks = {}
    #     for click in self.clicks:
    #         if click.obj_idx not in masks:
    #             masks[click.obj_idx] = np.zeros(coords.shape[0], dtype=bool)
    #         cube_mask = click.get_cube_mask(coords)
    #         masks[click.obj_idx] = np.logical_or(masks[click.obj_idx], cube_mask)
    #     logger.debug(f"Created masks for {len(masks)} objects")
    #     return masks
    def get_all_click_masks(self, coords: torch.Tensor) -> Dict[str, Dict[str, np.ndarray]]:
        """
        返回与 clickData 结构一致的嵌套掩码：
        masks[obj_key][part_key] -> bool ndarray
        """
        masks: Dict[str, Dict[str, np.ndarray]] = {}

        for click in self.clicks:
            # 跳过背景 obj 或 part（如果你有 '0' 约定）
            if click.obj_idx == 0 or getattr(click, "part_idx", 0) == 0:
                continue

            obj_key = str(click.obj_idx)
            part_key = str(click.part_idx)

            if obj_key not in masks:
                masks[obj_key] = {}
            if part_key not in masks[obj_key]:
                masks[obj_key][part_key] = np.zeros(coords.shape[0], dtype=bool)

            cube_mask = click.get_cube_mask(coords)
            masks[obj_key][part_key] = np.logical_or(masks[obj_key][part_key], cube_mask)

        logger.debug(
            f"Created part-level masks for {sum(len(v) for v in masks.values())} parts across {len(masks)} objects"
        )
        return masks


class PointCloudInference:
    def __init__(self, pretraining_weights='agile3d/weights/checkpoint1099.pth', voxel_size=0.05):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Using device: {self.device}")
        self.config = type('config', (), {
            'pretraining_weights': pretraining_weights,
            'voxel_size': voxel_size,
            'dialations': [1, 1, 1, 1],
            'conv1_kernel_size': 5,
            'bn_momentum': 0.02,
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
        with StepTimer("Loading model"):
            self.model = build_PinPoint3D(self.config)
            self.model.to(self.device)
            self.model.eval()
            if pretraining_weights:
                map_location = None if torch.cuda.is_available() else 'cpu'
                model_dict = torch.load(pretraining_weights, map_location=map_location)
                missing_keys, unexpected_keys = self.model.load_state_dict(model_dict['model'], strict=False)
                unexpected_keys = [k for k in unexpected_keys if not (k.endswith('total_params') or k.endswith('total_ops'))]
                if len(missing_keys) > 0:
                    logger.warning(f'Missing Keys: {missing_keys}')
                if len(unexpected_keys) > 0:
                    logger.warning(f'Unexpected Keys: {unexpected_keys}')
        logger.info(f"Model loaded from {pretraining_weights}")
        self.quantization_size = voxel_size
        self.point_cloud = None
        self.coords = None
        self.colors = None
        self.click_handler = ClickHandler()
        self.pcd_features = None
        self.aux = None
        self.coordinates = None
        self.pos_encodings_pcd = None
        self.inverse_map = None
        self.unique_map = None
        self.raw_coords_qv = None
        self.last_loaded_file = None
        self.point_type = None

    @timed
    def load_point_cloud(self, filepath: Union[str, Path]) -> None:
        logger.info(f"Loading point cloud from {filepath}")
        self.last_loaded_file = filepath
        if isinstance(filepath, Path):
            filepath = str(filepath)
        if not o3d.io.read_file_geometry_type(filepath):
            raise FileNotFoundError(f"Point cloud file not found or invalid: {filepath}")
        pcd_type = o3d.io.read_file_geometry_type(filepath)
        with StepTimer("Loading geometry"):
            if pcd_type == o3d.io.FileGeometry.CONTAINS_TRIANGLES:
                mesh = o3d.io.read_triangle_mesh(filepath)
                self.point_cloud = mesh
                self.coords = np.array(mesh.vertices)
                self.colors = np.array(mesh.vertex_colors) if mesh.has_vertex_colors() else np.ones((len(mesh.vertices), 3)) * 0.5
                self.point_type = "mesh"
                logger.info(f"Loaded mesh with {len(mesh.vertices)} vertices")
            elif pcd_type == o3d.io.FileGeometry.CONTAINS_POINTS:
                pcd = o3d.io.read_point_cloud(filepath)
                self.point_cloud = pcd
                self.coords = np.array(pcd.points)
                self.colors = np.array(pcd.colors) if pcd.has_colors() else np.ones((len(pcd.points), 3)) * 0.5
                self.point_type = "pointcloud"
                logger.info(f"Loaded point cloud with {len(pcd.points)} points")
            else:
                raise ValueError(f"Unknown point cloud format in {filepath}")
        self.click_handler = ClickHandler()
        with StepTimer("Preprocessing point cloud"):
            self._preprocess_point_cloud()

    def _preprocess_point_cloud(self) -> None:
        logger.info("Preprocessing point cloud for model inference")
        with StepTimer("Sparse quantization"):
            coords_qv, unique_map, inverse_map = ME.utils.sparse_quantize(
                coordinates=self.coords,
                quantization_size=self.quantization_size,
                return_index=True,
                return_inverse=True
            )
            logger.info(f"Quantized {len(self.coords)} points to {len(coords_qv)} voxels")
            self.coords_qv = coords_qv
            self.unique_map = unique_map
            self.inverse_map = inverse_map.to(self.device)
            self.colors_qv = torch.from_numpy(self.colors[unique_map]).float()
            self.raw_coords_qv = torch.from_numpy(self.coords[unique_map]).float().to(self.device)
        with StepTimer("Computing backbone features"):
            data = ME.SparseTensor(
                coordinates=ME.utils.batched_coordinates([self.coords_qv]),
                features=self.colors_qv,
                device=self.device
            )
            self.pcd_features, self.aux, self.coordinates, self.pos_encodings_pcd = self.model.forward_backbone(
                data, raw_coordinates=self.raw_coords_qv
            )
        logger.info(f"Processed point cloud features: {self.pcd_features.F.shape}")

    def load_clicks(self, filepath: str) -> None:
        self.click_handler.add_clicks_from_file(filepath, self.raw_coords_qv)
        logger.info(f"Loaded {len(self.click_handler.clicks)} clicks from {filepath}")

    def add_click(self, position: Union[np.ndarray, List[float], torch.Tensor], obj_idx: int, obj_name: str,
                  is_positive: bool = True, cube_size: float = 0.02) -> Click:
        logger.info(f"Adding click for object {obj_idx} ({obj_name}) at position {position}")
        click = self.click_handler.add_click(position, obj_idx, obj_name, is_positive, cube_size)
        click.find_nearest_point(self.raw_coords_qv)
        return click

    @timed
    # object_types: 列表，指定每个对象的类型。'point'类型的对象会被处理为背景
    def run_inference(self, object_types, target_id: int = None) -> np.ndarray:
        logger.info("Running inference")
        if self.coords is None or self.pcd_features is None:
            raise ValueError("Point cloud not loaded or processed. Call load_point_cloud first.")
        if not self.click_handler.clicks:
            raise ValueError("No clicks available. Add clicks before running inference.")
        with StepTimer("Processing clicks"):
            self.click_handler.process_clicks(self.raw_coords_qv)
            click_idx, click_time_idx, click_positions = self.click_handler.get_click_data_for_model()
            click_stats = {obj_id: len(indices) for obj_id, indices in click_idx.items()}
            logger.info(f"Click statistics by object: {click_stats}")
        with StepTimer("Running model forward pass"):
            outputs = self.model.forward_mask(
                self.pcd_features,
                self.aux,
                self.coordinates,
                self.pos_encodings_pcd,
                click_idx=[click_idx],
                click_time_idx=[click_time_idx],
                target_object_id=[1]
                # target_object_id=[1]
            )
        with StepTimer("Processing predictions"):
            pred = outputs['part_predictions_mask'][0].argmax(1)
            # pred = outputs['object_predictions_mask'][0].argmax(1)
            # for obj_id, cids in click_idx.items():
            #     if obj_id != '0':
            #         pred[cids] = int(obj_id)
            for obj_id, cids in click_idx.items():
                if obj_id != '0':  # Skip background class
                    for part_id, part_cids in cids.items():
                        if part_id != '0':
                            pred[part_cids] = int(part_id)
            click_masks = self.click_handler.get_all_click_masks(self.raw_coords_qv)
            # for obj_idx, mask in click_masks.items():
            #     if obj_idx != 0:
            #         pred[mask] = obj_idx
            for obj_key, part_dict in click_masks.items():
                # obj_key 是 str，这里不需要再用它去写 pred（避免覆盖 part 标签）
                for part_key, mask in part_dict.items():
                    if part_key == '0':
                        continue
                    m = torch.from_numpy(mask).to(pred.device)
                    pred[m] = int(part_key)   # 用 part_id 覆盖预测
            pred_full = pred[self.inverse_map]
            mask = pred_full.cpu().numpy()
            # 该段代码待验证直接使用可行性
            for idx, obj_type in enumerate(object_types, start=1):
                if obj_type == "point":  
                    mask[mask == idx] = 0   # 丢弃掉这个对象，改为背景
            # 该段代码待验证直接使用可行性
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_labels, counts = np.unique(mask, return_counts=True)
        for i, (label, count) in enumerate(zip(unique_labels, counts)):
            if label > 0:
                percentage = (count / len(mask)) * 100
                logger.info(f"Object {label}: {count} points ({percentage:.2f}%)")
        logger.info(
            f"Inference complete: Found {len(unique_labels) - 1} objects"
        )
        return mask

    def visualize_results(self, mask: np.ndarray) -> None:
        logger.info("Visualizing segmentation results")
        colors = self.colors.copy()
        obj_ids = np.unique(mask)
        obj_ids = [obj_id for obj_id in obj_ids if obj_id != 0]
        for obj_id in obj_ids:
            obj_mask = mask == obj_id
            colors[obj_mask] = get_obj_color(obj_id, normalize=True)
        logger.info(f"self.click_handler.clicks: {self.click_handler.clicks}")
        print(f"self.click_handler.clicks: {self.click_handler.clicks}")
        for click in self.click_handler.clicks:
            if click.id is not None:
                import torch as _torch
                coords_tensor = _torch.from_numpy(self.coords).float()
                cube_mask = click.get_cube_mask(coords_tensor)
                if click.obj_idx == 0 or click.part_idx == 0:
                    colors[cube_mask] = [0.1, 0.1, 0.1]
                else:
                    # obj_color = get_obj_color(click.obj_idx, normalize=True)
                    # bright_color = np.minimum(1.0, np.array(obj_color) * 1.5)
                    part_color = get_obj_color(click.part_idx, normalize=True)
                    bright_color = np.minimum(1.0, np.array(part_color) * 1.5)

                    colors[cube_mask] = bright_color
        vis_pcd = o3d.geometry.PointCloud()
        vis_pcd.points = o3d.utility.Vector3dVector(self.coords)
        vis_pcd.colors = o3d.utility.Vector3dVector(colors)
        if self.point_type == "pointcloud":
            vis_pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.005, max_nn=30))
        logger.info("Opening visualization window")
        o3d.visualization.draw_geometries([vis_pcd])

    @timed
    def save_results(self, mask: np.ndarray, output_dir: str, prefix: str = "") -> str:
        logger.info(f"Saving segmentation results to {output_dir}")
        import os
        os.makedirs(output_dir, exist_ok=True)
        scene_name = os.path.basename(os.path.splitext(str(self.last_loaded_file))[0]) if hasattr(self, 'last_loaded_file') else "unknown"
        if not prefix:
            prefix = scene_name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with StepTimer("Saving mask array"):
            filename = f"{prefix}_mask_{timestamp}.npy"
            mask_path = os.path.join(output_dir, filename)
            np.save(mask_path, mask)
            logger.info(f"Saved mask to {mask_path}")
        with StepTimer("Recording segmentation data"):
            record_file = os.path.join(output_dir, f"{prefix}_record.csv")
            with open(record_file, 'a') as f:
                now = datetime.now()
                num_obj = len(self.click_handler.click_idx.keys()) - 1
                num_click = sum([len(c) for c in self.click_handler.click_idx.values()])
                avg_clicks = round(num_click / max(num_obj, 1), 1)
                sample_iou = 'NA'
                line = now.strftime("%Y-%m-%d-%H-%M-%S") + '  ' + scene_name + '  NumObjects:' + str(num_obj) + '  AvgNumClicks:' + str(avg_clicks) + '  mIoU:' + sample_iou + '\n'
                f.write(line)
                logger.info(line.strip())
        clicks_file = os.path.join(output_dir, f"{prefix}_clicks_{timestamp}.json")
        self.click_handler.save_clicks_to_file(clicks_file)
        logger.info(f"Saved clicks to {clicks_file}")
        with StepTimer("Creating colored point cloud"):
            colors = self.colors.copy()
            obj_ids = np.unique(mask)
            for obj_id in obj_ids:
                if obj_id != 0:
                    obj_mask = mask == obj_id
                    colors[obj_mask] = get_obj_color(obj_id, normalize=True)
            if self.point_type == "pointcloud":
                vis_pcd = o3d.geometry.PointCloud()
                vis_pcd.points = o3d.utility.Vector3dVector(self.coords)
                vis_pcd.colors = o3d.utility.Vector3dVector(colors)
                colored_ply_file = os.path.join(output_dir, f"{prefix}_result_{timestamp}.ply")
                o3d.io.write_point_cloud(colored_ply_file, vis_pcd)
                logger.info(f"Saved colored point cloud to {colored_ply_file}")
            else:
                vis_mesh = o3d.geometry.TriangleMesh()
                vis_mesh.vertices = o3d.utility.Vector3dVector(self.coords)
                vis_mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                colored_ply_file = os.path.join(output_dir, f"{prefix}_result_{timestamp}.ply")
                o3d.io.write_triangle_mesh(colored_ply_file, vis_mesh)
                logger.info(f"Saved colored mesh to {colored_ply_file}")
        return colored_ply_file


@timed
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
    logger.info(f"Starting inference on: {point_cloud_path}")
    logger.info(f"Using device: {torch.device('cuda' if torch.cuda.is_available() else 'cpu')}")
    with StepTimer("Initializing inference"):
        inference = PointCloudInference(
            pretraining_weights=pretraining_weights,
            voxel_size=voxel_size
        )
    with StepTimer("Loading point cloud"):
        inference.load_point_cloud(point_cloud_path)
    if clicks_file:
        with StepTimer("Loading clicks from file"):
            inference.load_clicks(clicks_file)
    elif click_positions and click_obj_indices:
        with StepTimer("Adding manual clicks"):
            if len(click_positions) != len(click_obj_indices):
                raise ValueError("Number of click positions and object indices must match")
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
            logger.info(f"Added {len(click_positions)} manual clicks")
    if inference.click_handler.clicks:
        with StepTimer("Running inference"):
            mask = inference.run_inference()
        with StepTimer("Saving results"):
            result_path = inference.save_results(mask, output_dir)
        if visualize:
            with StepTimer("Visualizing results"):
                inference.visualize_results(mask)
        return result_path, mask
    else:
        logger.warning("No clicks provided. Please provide clicks via clicks_file or click_positions.")
        return None, None


