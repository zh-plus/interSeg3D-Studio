from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from core.services.recognition_service import RecognitionService
from core.state.session_manager import SessionManager
from core.models.requests import MaskObjDetectionRequest, UpdateObjectsRequest
from core.models.responses import ObjectRecognitionResponse, UpdateObjectsResponse
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# Import the real dependencies
from api.dependencies import get_recognition_service, get_session_manager

router = APIRouter(prefix="/recognition", tags=["recognition"])

@router.post("/mask_obj_recognition", response_model=ObjectRecognitionResponse)
async def run_mask_obj_recognition(
    request: MaskObjDetectionRequest,
    recognition_service: RecognitionService = Depends(get_recognition_service),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Run mask-based object recognition on the current point cloud using provided mask.
    
    The request body should contain a field "mask" that is a list of integers where:
      - 0 represents the background
      - 1 represents the first object
      - 2 represents the second object, and so on.
    
    Returns:
      - A list of JSON objects with keys "selected_views", "description", "label", and "cost",
        one for each unique object ID in the mask (excluding background).
    """
    session = session_manager.get_current_session()
    
    if not session.point_cloud:
        raise HTTPException(400, "No point cloud loaded. Please upload a point cloud first.")
    
    try:
        logger.info("Starting mask-based object recognition")
        
        # Run object recognition
        object_info = await recognition_service.recognize_objects_from_mask(
            str(session.point_cloud.file_path), 
            request
        )
        
        # Store results in session
        session.object_info = object_info
        
        # Convert to serializable format for response
        result = []
        for obj in object_info:
            result.append({
                "obj_id": obj.obj_id,
                "label": obj.label,
                "description": obj.description,
                "selected_views": obj.selected_views,
                "cost": obj.cost
            })
        
        logger.info(f"Object recognition completed for {len(result)} objects")
        
        return ObjectRecognitionResponse(
            message="Mask object recognition completed successfully",
            result=result
        )
        
    except ValueError as e:
        logger.error(f"Validation error in object recognition: {str(e)}")
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error running mask object recognition: {str(e)}")
        raise HTTPException(500, f"Error running mask object recognition: {str(e)}")

@router.post("/update_objects", response_model=UpdateObjectsResponse)
async def update_objects(
    request: UpdateObjectsRequest,
    recognition_service: RecognitionService = Depends(get_recognition_service),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Update object information (labels, descriptions) for the current session.
    
    The request body should contain a list of objects with id, name, and description fields.
    """
    session = session_manager.get_current_session()
    
    try:
        logger.info(f"Updating object information for {len(request.objects)} objects")
        
        # Update object information
        updated_objects = recognition_service.update_object_info(
            request, 
            session.object_info or []
        )
        
        # Store updated information in session
        session.object_info = updated_objects
        
        logger.info(f"Updated information for {len(updated_objects)} objects")
        
        return UpdateObjectsResponse(
            message=f"Successfully updated information for {len(updated_objects)} objects",
            updated_count=len(updated_objects)
        )
        
    except Exception as e:
        logger.error(f"Error updating objects: {str(e)}")
        raise HTTPException(500, f"Error updating objects: {str(e)}")
@router.get("/stats")
async def get_recognition_stats(
    recognition_service: RecognitionService = Depends(get_recognition_service),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Get statistics about object recognition results"""
    session = session_manager.get_current_session()
    
    if not session.object_info:
        return {"message": "No object recognition results available"}
    
    stats = recognition_service.get_recognition_stats(session.object_info)
    return stats

