from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from core.services.export_service import ExportService
from core.services.inference_service import InferenceService
from core.state.session_manager import SessionManager
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# Import the real dependencies
from api.dependencies import get_export_service, get_inference_service, get_session_manager

router = APIRouter(prefix="/download", tags=["download"])

@router.get("/results")
async def download_results(
    export_service: ExportService = Depends(get_export_service),
    inference_service: InferenceService = Depends(get_inference_service),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Download the segmentation results as a zip file containing:
    1. A PLY file with uncolored scene and colored objects
    2. A JSON file with object labels, descriptions, colors, and other metadata
    """
    session = session_manager.get_current_session()
    
    # Validate session state
    if not session.point_cloud:
        raise HTTPException(400, "No point cloud loaded. Please upload a point cloud first.")
    
    if not session.segmentation_result:
        raise HTTPException(400, "No results available. Please run inference first.")
    
    try:
        logger.info("Creating download package")
        
        # Create download package
        file_generator = await export_service.create_download_package(
            point_cloud_data=session.point_cloud,
            segmentation_result=session.segmentation_result,
            object_info=session.object_info or [],
            inference_engine=inference_service.inference_engine
        )
        
        headers = {
            'Content-Disposition': 'attachment; filename="segmentation_results.zip"',
            'Content-Type': 'application/zip'
        }
        
        logger.info("Streaming download package to client")
        
        return StreamingResponse(
            file_generator,
            headers=headers,
            media_type='application/zip'
        )
        
    except Exception as e:
        logger.error(f"Error creating download package: {str(e)}")
        raise HTTPException(500, f"Error downloading results: {str(e)}")

@router.get("/info")
async def get_download_info(
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Get information about available downloads"""
    session = session_manager.get_current_session()
    
    return {
        "available": session.segmentation_result is not None,
        "has_point_cloud": session.point_cloud is not None,
        "has_object_info": len(session.object_info or []) > 0,
        "object_count": len(session.object_info or [])
    }
