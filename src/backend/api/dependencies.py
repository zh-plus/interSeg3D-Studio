from fastapi import Depends, Request

from core.services.point_cloud_service import PointCloudService
from core.services.inference_service import InferenceService
from core.services.recognition_service import RecognitionService
from core.services.export_service import ExportService
from core.state.session_manager import SessionManager

def get_container(request: Request):
    """Get the dependency injection container from the app"""
    return request.app.container

def get_point_cloud_service(container=Depends(get_container)) -> PointCloudService:
    """Get point cloud service from container"""
    return container.point_cloud_service()

def get_inference_service(container=Depends(get_container)) -> InferenceService:
    """Get inference service from container"""
    return container.inference_service()

def get_recognition_service(container=Depends(get_container)) -> RecognitionService:
    """Get recognition service from container"""
    return container.recognition_service()

def get_export_service(container=Depends(get_container)) -> ExportService:
    """Get export service from container"""
    return container.export_service()

def get_session_manager(container=Depends(get_container)) -> SessionManager:
    """Get session manager from container"""
    return container.session_manager()
