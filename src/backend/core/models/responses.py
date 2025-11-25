from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from core.models.domain import BoundingBox

class UploadResponse(BaseModel):
    message: str
    filename: str
    point_count: int
    bounding_box: BoundingBox

class InferenceResponse(BaseModel):
    message: str
    # Keep snake_case internally but expose camelCase in JSON to match frontend
    segmented_point_cloud: Dict[str, Any] = Field(serialization_alias="segmentedPointCloud")

class ObjectRecognitionResponse(BaseModel):
    message: str
    result: List[Dict[str, Any]]

class UpdateObjectsResponse(BaseModel):
    message: str
    updated_count: int

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: str
