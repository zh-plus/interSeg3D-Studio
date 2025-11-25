from typing import Dict, List, Any, Optional
import torch
import numpy as np

from core.models.domain import PointCloudData, SegmentationResult, ClickData
from core.models.requests import InferenceRequest
from infrastructure.inference.engine import PointCloudInference, ClickHandler, Click
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

class InferenceService:
    """Service for handling AI inference operations"""
    
    def __init__(self, model_weights_path: str, voxel_size: float = 0.05):
        self.model_weights_path = model_weights_path
        self.voxel_size = voxel_size
        self.inference_engine: Optional[PointCloudInference] = None
        self.current_point_cloud_path: Optional[str] = None

        self.accumulated_labels: Optional[np.ndarray] = None
        self.result_version: int = 0
        self.target_label_offset_map: Dict[int, int] = {}
        self.TARGET_OFFSET_STEP = 100

    async def initialize_for_point_cloud(self, point_cloud_data: PointCloudData) -> None:
        """Initialize the inference engine for a specific point cloud"""
        logger.info("Initializing inference engine for point cloud")
        
        try:
            # Create new inference engine
            self.inference_engine = PointCloudInference(
                pretraining_weights=self.model_weights_path,
                voxel_size=self.voxel_size
            )
            
            # Load the point cloud into the inference engine
            self.inference_engine.load_point_cloud(str(point_cloud_data.file_path))
            self.current_point_cloud_path = str(point_cloud_data.file_path)
            
            self.accumulated_labels = None
            self.result_version = 0
            self.target_label_offset_map.clear()

            logger.info("Inference engine initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize inference engine: {e}")
            self.inference_engine = None
            raise e
    
    def is_initialized(self) -> bool:
        """Check if inference engine is initialized"""
        return self.inference_engine is not None
    

    async def run_inference(self, request: InferenceRequest) -> SegmentationResult:
        """Run segmentation inference with click data (supports part/object nesting)"""
        if not self.inference_engine:
            raise ValueError("Inference engine not initialized. Please upload a point cloud first.")
        
        logger.info("Running inference with click data (part/object nesting)")
        
        try:
            # Detailed logging of received data
            logger.info(f"Received clickData keys: {list(request.clickData.keys())}")
            logger.info(f"clickData type: {type(request.clickData)}")
            
            # Check if clickPositions exists
            if "clickPositions" not in request.clickData:
                error_msg = f"clickPositions not found in clickData. Available keys: {list(request.clickData.keys())}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            click_positions = request.clickData["clickPositions"]
            logger.info(f"clickPositions type: {type(click_positions)}, length: {len(click_positions) if isinstance(click_positions, dict) else 'N/A'}")
            logger.info(f"clickPositions content: {click_positions}")
            
            if not isinstance(click_positions, dict):
                error_msg = f"clickPositions is not a dict, got {type(click_positions)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            if len(click_positions) == 0:
                error_msg = "clickPositions is empty"
                logger.error(error_msg)
                raise ValueError("No clicks available. Add clicks before running inference.")
            
            # Check clickTimeIdx
            click_time_idx = request.clickData.get("clickTimeIdx", {})
            logger.info(f"clickTimeIdx type: {type(click_time_idx)}, length: {len(click_time_idx) if isinstance(click_time_idx, dict) else 'N/A'}")
            
            target_id = int(request.clickData.get("targetId", 1))
            logger.info(f"Using target_id: {target_id}")
            
            click_handler = ClickHandler()
            total_clicks_added = 0
            
            # Process nested part/object structure
            for obj_idx_str, part_idxs in click_positions.items():
                logger.info(f"Processing object {obj_idx_str}, part_idxs type: {type(part_idxs)}, value: {part_idxs}")
                
                # Type check
                if not isinstance(part_idxs, dict):
                    logger.warning(f"part_idxs for object {obj_idx_str} is not a dict (type: {type(part_idxs)}), skipping")
                    continue
                
                if part_idxs is None or len(part_idxs) == 0:
                    logger.debug(f"Object {obj_idx_str} has no parts or is empty, skipping")
                    continue
                
                obj_idx = int(obj_idx_str)
                obj_name = "background" if obj_idx == 0 else f"object_{obj_idx}"
                
                # Safe access to time indices
                if obj_idx_str not in click_time_idx:
                    logger.warning(f"No time indices for object {obj_idx_str}, skipping")
                    continue
                
                part_idx_time_indices = click_time_idx[obj_idx_str]
                if not isinstance(part_idx_time_indices, dict):
                    logger.warning(f"Time indices for object {obj_idx_str} is not a dict, skipping")
                    continue
                
                logger.info(f"Processing object {obj_idx_str} with {len(part_idxs)} parts: {list(part_idxs.keys())}")
                
                for part_idx, positions in part_idxs.items():
                    logger.debug(f"  Processing part {part_idx}, positions count: {len(positions) if positions else 0}")
                    
                    # Skip part '0' for non-background objects
                    if part_idx == '0' and obj_idx != 0:
                        logger.debug(f"  Skipping part '0' for non-background object {obj_idx}")
                        continue
                    
                    # Safe access to time indices
                    if part_idx not in part_idx_time_indices:
                        logger.warning(f"  No time indices for object {obj_idx_str}, part {part_idx}, skipping")
                        continue
                    
                    time_indices = part_idx_time_indices[part_idx]
                    
                    # Check positions
                    if not positions or len(positions) == 0:
                        logger.debug(f"  Object {obj_idx_str}, part {part_idx} has no positions, skipping")
                        continue
                    
                    # Ensure time_indices length matches
                    if len(time_indices) != len(positions):
                        logger.warning(f"  Time indices length {len(time_indices)} != positions length {len(positions)} for obj {obj_idx_str}, part {part_idx}")
                        min_len = min(len(time_indices), len(positions))
                        time_indices = time_indices[:min_len]
                        positions = positions[:min_len]
                    
                    logger.info(f"  Creating {len(positions)} clicks for object {obj_idx_str}, part {part_idx}")
                    
                    for i, pos in enumerate(positions):
                        try:
                            click = Click(
                                position=torch.tensor(pos, dtype=torch.float32),
                                obj_idx=obj_idx,
                                part_idx=int(part_idx), 
                                obj_name=obj_name,
                                time_idx=time_indices[i] if i < len(time_indices) else 0,
                                is_positive=True,
                                cube_size=request.cubeSize
                            )
                            click_handler.clicks.append(click)
                            click.find_nearest_point(self.inference_engine.raw_coords_qv)
                            click_handler._update_click_dicts(click)
                            total_clicks_added += 1
                        except Exception as e:
                            logger.error(f"  Error creating click {i} for object {obj_idx_str}, part {part_idx}: {e}")
                            raise
            
            # Critical check before proceeding
            logger.info(f"Total clicks created: {total_clicks_added}, click_handler.clicks length: {len(click_handler.clicks)}")
            
            if len(click_handler.clicks) == 0:
                error_msg = f"No clicks created! clickPositions structure: {click_positions}, clickTimeIdx structure: {click_time_idx}"
                logger.error(error_msg)
                raise ValueError("No clicks available. Add clicks before running inference.")
            
            logger.info(f"Successfully created {len(click_handler.clicks)} clicks, proceeding with inference")
            
            self.inference_engine.click_handler = click_handler
            new_out = self.inference_engine.run_inference(
                object_types=request.objectTypes or ['object'], 
                target_id=target_id
            )
            new_out = np.asarray(new_out)
            if new_out.dtype == np.bool_:
                new_out = new_out.astype(np.int32)
            elif not np.issubdtype(new_out.dtype, np.integer):
                new_out = new_out.astype(np.int32, copy=False)
            
            if target_id not in self.target_label_offset_map:
                self.target_label_offset_map[target_id] = target_id * self.TARGET_OFFSET_STEP
            offset = self.target_label_offset_map[target_id]
            
            pos_idx = new_out > 0
            if np.any(pos_idx):
                new_out[pos_idx] = new_out[pos_idx].astype(np.int64) + int(offset)
            new_out = new_out.astype(np.int32, copy=False)
            
            if self.accumulated_labels is None or self.accumulated_labels.shape != new_out.shape:
                self.accumulated_labels = np.zeros_like(new_out, dtype=np.int32)
            
            prev_labels = self.accumulated_labels.copy()
            
            tgt_span = (self.accumulated_labels >= offset + 1) & \
                      (self.accumulated_labels < offset + self.TARGET_OFFSET_STEP)
            self.accumulated_labels[tgt_span] = 0
            
            write_idx = new_out > 0
            self.accumulated_labels[write_idx] = new_out[write_idx]
            
            changed_mask = (self.accumulated_labels != prev_labels)
            changed_idx = np.flatnonzero(changed_mask).astype(int).tolist()
            
            colored_ply = self.inference_engine.save_results(
                self.accumulated_labels, 
                output_dir="./outputs",
                prefix=f"web_session_{self.current_point_cloud_path.split('/')[-1].split('.')[0] if self.current_point_cloud_path else 'unknown'}"
            )
            
            unique_labels, counts = np.unique(self.accumulated_labels, return_counts=True)
            object_counts = {}
            for label, count in zip(unique_labels, counts):
                if label > 0:
                    object_counts[int(label)] = int(count)
            
            self.result_version += 1
            
            result = SegmentationResult(
                mask=self.accumulated_labels,
                result_path=colored_ply,
                object_counts=object_counts,
                metadata={
                    "num_objects": len(object_counts),
                    "total_clicks": len(click_handler.clicks),
                    "cube_size": request.cubeSize,
                    "result_version": self.result_version,
                    "target_id": target_id,
                    "changed_idx": changed_idx
                }
            )
            
            logger.info(f"Inference completed: found {len(object_counts)} objects, version {self.result_version}")
            return result
            
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            raise e
    
    # async def run_inference(self, request: InferenceRequest) -> SegmentationResult:
    #     """Run segmentation inference with click data"""
    #     if not self.inference_engine:
    #         raise ValueError("Inference engine not initialized. Please upload a point cloud first.")
        
    #     logger.info("Running inference with click data")
        
    #     try:
    #         # Convert click data to format expected by inference engine
    #         click_handler = ClickHandler()
            
    #         # Process click positions and create Click objects
    #         for obj_idx_str, positions in request.clickData["clickPositions"].items():
    #             obj_idx = int(obj_idx_str)
    #             obj_name = "background" if obj_idx == 0 else f"object_{obj_idx}"
                
    #             # Get time indices for this object
    #             time_indices = request.clickData["clickTimeIdx"][obj_idx_str]
                
    #             for i, pos in enumerate(positions):
    #                 # Create click and add to handler
    #                 click = Click(
    #                     position=torch.tensor(pos, dtype=torch.float32),
    #                     obj_idx=obj_idx,
    #                     obj_name=obj_name,
    #                     time_idx=time_indices[i],
    #                     is_positive=True,
    #                     cube_size=request.cubeSize
    #                 )
    #                 click_handler.clicks.append(click)
                    
    #                 # Find nearest point in the point cloud
    #                 click.find_nearest_point(self.inference_engine.raw_coords_qv)
                    
    #                 # Update model-compatible formats
    #                 click_handler._update_click_dicts(click)
            
    #         # Set clicks in the inference object
    #         self.inference_engine.click_handler = click_handler
            
    #         # Run inference
    #         mask = self.inference_engine.run_inference(object_types = request.objectTypes)
    #         # mask = self.inference_engine.run_inference()
    #         # Save results
    #         colored_ply = self.inference_engine.save_results(
    #             mask,
    #             output_dir="./outputs",
    #             prefix=f"web_session_{self.current_point_cloud_path.split('/')[-1].split('.')[0] if self.current_point_cloud_path else 'unknown'}"
    #         )
            
    #         # Calculate object counts
    #         unique_labels, counts = np.unique(mask, return_counts=True)
    #         object_counts = {}
    #         for label, count in zip(unique_labels, counts):
    #             if label > 0:  # Skip background
    #                 object_counts[int(label)] = int(count)
            
    #         result = SegmentationResult(
    #             mask=mask,
    #             result_path=colored_ply,
    #             object_counts=object_counts,
    #             metadata={
    #                 "num_objects": len(object_counts),
    #                 "total_clicks": len(click_handler.clicks),
    #                 "cube_size": request.cubeSize
    #             }
    #         )
            
    #         logger.info(f"Inference completed: found {len(object_counts)} objects")
    #         return result
            
    #     except Exception as e:
    #         logger.error(f"Inference failed: {e}")
    #         raise e
    
    def get_inference_status(self) -> Dict[str, Any]:
        """Get current status of the inference engine"""
        return {
            "initialized": self.is_initialized(),
            "model_weights": self.model_weights_path,
            "voxel_size": self.voxel_size,
            "current_point_cloud": self.current_point_cloud_path,
            "device": str(torch.device('cuda' if torch.cuda.is_available() else 'cpu')),
            "result_version": self.result_version,
            "accumulated_labels_shape": list(self.accumulated_labels.shape) if self.accumulated_labels is not None else None
        }
    
    def clear(self) -> None:
        """Clear the current inference engine"""
        self.inference_engine = None
        self.current_point_cloud_path = None
        self.accumulated_labels = None
        self.result_version = 0
        self.target_label_offset_map.clear()
        logger.info("Inference engine cleared")
