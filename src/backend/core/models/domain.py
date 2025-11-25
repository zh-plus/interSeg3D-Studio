from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import numpy as np
from pathlib import Path

@dataclass
class BoundingBox:
    min_coords: List[float]
    max_coords: List[float]
    
    @classmethod
    def from_coords(cls, coords: np.ndarray) -> 'BoundingBox':
        return cls(
            min_coords=coords.min(axis=0).tolist(),
            max_coords=coords.max(axis=0).tolist()
        )

@dataclass
class PointCloudData:
    coords: np.ndarray
    colors: np.ndarray
    is_point_cloud: bool
    point_count: int
    bounding_box: BoundingBox
    file_path: Path
    filename: str = ""
    
    def __post_init__(self):
        if not self.filename:
            self.filename = self.file_path.name

@dataclass
class ObjectInfo:
    obj_id: int
    label: str
    type: str
    position: List[float]
    description: str = ""
    color: List[float] = field(default_factory=list)
    cost: Optional[float] = None
    selected_views: List[int] = field(default_factory=list)

@dataclass
class SegmentationResult:
    mask: np.ndarray
    result_path: str
    object_counts: Dict[int, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SessionState:
    session_id: str
    point_cloud: Optional[PointCloudData] = None
    segmentation_result: Optional[SegmentationResult] = None
    object_info: List[ObjectInfo] = field(default_factory=list)
    inference_initialized: bool = False
    
    def clear_results(self):
        """Clear segmentation results while keeping point cloud"""
        self.segmentation_result = None
        self.object_info = []
    
    def clear_all(self):
        """Clear all session data"""
        self.point_cloud = None
        self.segmentation_result = None
        self.object_info = []
        self.inference_initialized = False

@dataclass
class ClickData:
    position: List[float]
    obj_idx: int
    obj_name: str
    time_idx: int
    is_positive: bool = True
    cube_size: float = 0.02
