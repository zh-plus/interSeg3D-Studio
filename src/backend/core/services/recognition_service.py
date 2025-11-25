import multiprocessing
from typing import List, Dict, Any
import numpy as np
import os
from PIL import Image

from core.models.domain import ObjectInfo, SegmentationResult
from core.models.requests import MaskObjDetectionRequest, UpdateObjectsRequest
from infrastructure.llm.base import LLMClient
from infrastructure.rendering.view_renderer import ViewRenderer
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

class RecognitionService:
    """Service for object recognition using LLM and view rendering"""
    
    def __init__(self, llm_client: LLMClient, view_renderer: ViewRenderer, max_workers: int = 8):
        self.llm_client = llm_client
        self.view_renderer = view_renderer
        self.max_workers = max_workers
    
    async def recognize_objects_from_mask(
        self, 
        point_cloud_path: str, 
        request: MaskObjDetectionRequest,
        use_multiprocessing: bool = False
    ) -> List[ObjectInfo]:
        """Run object recognition on masked objects.
        
        Args:
            point_cloud_path: Path to the point cloud file.
            request: Request containing the mask.
            use_multiprocessing: Whether to use multiprocessing for per-object recognition.
        """
        logger.info("Starting mask-based object recognition")
        
        mask_np = np.array(request.mask, dtype=int)
        
        # Find unique object IDs, excluding background (0)
        unique_obj_ids = np.unique(mask_np)
        unique_obj_ids = unique_obj_ids[unique_obj_ids > 0]
        # Ensure Python int types to avoid numpy.int64 leaking into responses
        unique_obj_ids = [int(x) for x in unique_obj_ids.tolist()]
        
        if len(unique_obj_ids) == 0:
            raise ValueError("No objects found in the mask (all values are 0/background)")
        
        # For reliability, use sequential async pipeline leveraging internal services
        if use_multiprocessing:
            logger.warning("Multiprocessing mode is not supported in the refactored pipeline; falling back to sequential mode")
        
        results = []
        for obj_id in unique_obj_ids:
            try:
                view_output_dir = f"./object_views/obj_{int(obj_id)}"
                view_paths = self.view_renderer.render_object_views(
                    point_cloud_path=point_cloud_path,
                    mask=mask_np,
                    obj_id=int(obj_id),
                    output_dir=view_output_dir,
                    num_positions=8,
                    mask_mode="outline"
                )
                images = []
                for path in view_paths:
                    if os.path.exists(path):
                        try:
                            images.append(Image.open(path))
                        except Exception as e:
                            logger.error(f"Error opening {path}: {e}")
                    else:
                        logger.warning(f"Warning: {path} not found.")
                prompt = (
                    "I have uploaded a series of rendered views of a scene generated using the 'outline' mask mode. "
                    "Do not describe the mask itself, which is used to highlight the object of interest. "
                    "Please analyze these images and select the views with the best quality. Then, according to these good quality images, provide the following:\n"
                    "1. A detailed description of the object along with the surrounding scene or any nearby objects.\n"
                    "2. A concise label for the masked object."
                    "Note, for the description, directly mention the object's attributes, such as color, shape, size, and any other relevant details. For example: 'A black sofa with...' Do not use 'This is a ...' or 'This image shows a ...' in the description."
                    "Also, describe the relationship between the object and the surrounding scene or any nearby objects. For example: 'The sofa is placed in front of a desk.'"
                    "Never use 'in the scene' or 'in the image' in the description."
                )
                response = await self.llm_client.analyze_images(images, prompt)
                if 'selected_views' not in response:
                    response['selected_views'] = []
                result = {
                    'obj_id': int(obj_id),
                    'label': response.get('label', f'Object {int(obj_id)}'),
                    'description': response.get('description', ''),
                    'selected_views': response.get('selected_views', []),
                    'cost': response.get('cost', 0.0)
                }
                results.append(result)
            except Exception as e:
                logger.error(f"Error recognizing object {int(obj_id)}: {e}")
                results.append({
                    'obj_id': int(obj_id),
                    'label': f'Object {int(obj_id)}',
                    'description': 'Recognition failed',
                    'selected_views': [],
                    'cost': 0.0
                })
        
        # Convert results to ObjectInfo objects
        object_info_list = []
        for result in results:
            if result:
                # Normalize types to plain Python builtins
                obj_id_val = int(result.get('obj_id', 0))
                label_val = result.get('label', 'Unknown Object')
                description_val = result.get('description', '')
                selected_views_val = result.get('selected_views', [])
                if isinstance(selected_views_val, np.ndarray):
                    selected_views_val = selected_views_val.astype(int).tolist()
                else:
                    try:
                        selected_views_val = [int(v) for v in selected_views_val]
                    except Exception:
                        selected_views_val = []
                cost_val = result.get('cost', 0.0)
                try:
                    cost_val = float(cost_val)
                except Exception:
                    cost_val = 0.0
                object_info = ObjectInfo(
                    obj_id=obj_id_val,
                    label=label_val,
                    type="unknown",
                    position=[],
                    description=description_val,
                    selected_views=selected_views_val,
                    cost=cost_val
                )
                object_info_list.append(object_info)
        
        logger.info(f"Completed object recognition for {len(object_info_list)} objects")
        return object_info_list
    
    def _recognize_single_object(self, args) -> Dict[str, Any]:
        """Deprecated: kept for compatibility; not used in refactored flow."""
        obj_id, point_cloud_path, mask_np = args
        logger.warning("_recognize_single_object legacy path called; returning failure placeholder")
        return {
            'obj_id': int(obj_id),
            'label': f'Object {int(obj_id)}',
            'description': 'Recognition not executed in legacy path',
            'selected_views': [],
            'cost': 0.0
        }
    
    def update_object_info(
        self, 
        request: UpdateObjectsRequest, 
        current_object_info: List[ObjectInfo]
    ) -> List[ObjectInfo]:
        """Update object information with new labels and descriptions"""
        logger.info(f"Updating information for {len(request.objects)} objects")
        
        # Create a mapping of existing object information by ID
        obj_info_map = {obj.obj_id: obj for obj in current_object_info}
        
        # Update the objects with new information
        updated_objects = []
        for obj_data in request.objects:
            if 'id' not in obj_data:
                continue
            
            obj_id = obj_data['id']
            
            # If this object exists in our current info, update it
            if obj_id in obj_info_map:
                existing_obj = obj_info_map[obj_id]
                # Update name and description
                if 'name' in obj_data:
                    existing_obj.label = obj_data['name']
                if 'description' in obj_data:
                    existing_obj.description = obj_data['description']
                if 'type' in obj_data:
                    existing_obj.type = obj_data['type']
                if 'position' in obj_data:
                    existing_obj.position = obj_data['position']
                updated_objects.append(existing_obj)
            else:
                # This is a new object, add it with minimal information
                new_obj = ObjectInfo(
                    obj_id=obj_id,
                    label=obj_data.get('name', f"Object {obj_id}"),
                    description=obj_data.get('description', ''),
                    type=obj_data.get('type', "unknown"),
                    position=obj_data.get('position', []),
                    selected_views=[]
                )
                updated_objects.append(new_obj)
        
        logger.info(f"Updated information for {len(updated_objects)} objects")
        return updated_objects
    
    def get_recognition_stats(self, object_info: List[ObjectInfo]) -> Dict[str, Any]:
        """Get statistics about object recognition results"""
        if not object_info:
            return {"total_objects": 0, "total_cost": 0.0}
        
        total_cost = sum(obj.cost or 0.0 for obj in object_info)
        
        return {
            "total_objects": len(object_info),
            "total_cost": total_cost,
            "average_cost": total_cost / len(object_info) if object_info else 0.0,
            "objects_with_descriptions": len([obj for obj in object_info if obj.description]),
        }
