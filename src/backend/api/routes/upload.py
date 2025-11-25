from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from fastapi.responses import JSONResponse

from core.services.point_cloud_service import PointCloudService
from core.services.inference_service import InferenceService
from core.state.session_manager import SessionManager
from core.models.responses import UploadResponse
from config.settings import settings
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# Import the real dependencies
from api.dependencies import get_point_cloud_service, get_inference_service, get_session_manager

router = APIRouter(prefix="/upload", tags=["upload"])

@router.post("/", response_model=UploadResponse)
async def upload_point_cloud(
    file: UploadFile = File(...),
    point_cloud_service: PointCloudService = Depends(get_point_cloud_service),
    inference_service: InferenceService = Depends(get_inference_service),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Upload a point cloud file (PLY format)"""
    
    logger.info(f"Received upload request for file: {file.filename}")
    
    # Validate file
    if not point_cloud_service.validate_point_cloud_file(file.filename):
        raise HTTPException(400, "Only PLY files are supported")
    
    # Check file size (if needed)
    if hasattr(file, 'size') and file.size > settings.max_file_size:
        raise HTTPException(400, f"File too large. Maximum size: {settings.max_file_size / (1024*1024):.1f}MB")
    
    try:
        # Load point cloud data
        point_cloud_data = await point_cloud_service.save_and_load_upload(file)
        
        # Store in session
        session = session_manager.get_current_session()
        session.point_cloud = point_cloud_data
        session.clear_results()  # Clear any previous results
        
        # Initialize inference
        await inference_service.initialize_for_point_cloud(point_cloud_data)
        session.inference_initialized = True
        
        logger.info(f"Successfully processed upload: {file.filename}")
        
        return UploadResponse(
            message="File uploaded successfully",
            filename=file.filename,
            point_count=point_cloud_data.point_count,
            bounding_box=point_cloud_data.bounding_box
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        raise HTTPException(500, f"Error processing file: {str(e)}")

@router.get("/status")
async def get_upload_status(
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Get current upload status"""
    session = session_manager.get_current_session()
    
    if not session.point_cloud:
        return {"uploaded": False, "message": "No file uploaded"}
    
    return {
        "uploaded": True,
        "filename": session.point_cloud.filename,
        "point_count": session.point_cloud.point_count,
        "inference_ready": session.inference_initialized
    }
