from pydantic import BaseModel, field_validator
from typing import Dict, List, Any, Optional

class InferenceRequest(BaseModel):
    clickData: Dict[str, Any]  # clickIdx, clickTimeIdx, clickPositions
    cubeSize: float
    objectNames: List[str]
    # objectTypes: List[str]
    objectTypes: Optional[List[str]] = None
    
    @field_validator('cubeSize')
    @classmethod
    def validate_cube_size(cls, v):
        if v <= 0 or v > 1.0:
            raise ValueError('cubeSize must be between 0 and 1.0')
        return v

class MaskObjDetectionRequest(BaseModel):
    # "mask" is a list of integers where 0 is background, 1 is first object, 2 is second object, etc.
    mask: List[int]
    
    @field_validator('mask')
    @classmethod
    def validate_mask(cls, v):
        if not v:
            raise ValueError('mask cannot be empty')
        if not all(isinstance(x, int) and x >= 0 for x in v):
            raise ValueError('mask must contain non-negative integers')
        return v

class UpdateObjectsRequest(BaseModel):
    objects: List[Dict[str, Any]]
    
    @field_validator('objects')
    @classmethod
    def validate_objects(cls, v):
        for obj in v:
            if 'id' not in obj:
                raise ValueError('Each object must have an id field')
        return v
