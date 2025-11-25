from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from core.services.inference_service import InferenceService
from core.state.session_manager import SessionManager
from core.models.requests import InferenceRequest
from core.models.responses import InferenceResponse
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# Import the real dependencies
from api.dependencies import get_inference_service, get_session_manager

router = APIRouter(prefix="/infer", tags=["inference"])

@router.post("/", response_model=InferenceResponse)
async def run_inference(
    request: InferenceRequest,
    inference_service: InferenceService = Depends(get_inference_service),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Run inference on the current point cloud with the provided click data"""
    
    logger.info("Received inference request")
    
    # Get current session
    session = session_manager.get_current_session()
    
    # Validate session state
    if not session.point_cloud:
        raise HTTPException(400, "No point cloud loaded. Please upload a point cloud first.")
    
    if not session.inference_initialized:
        raise HTTPException(400, "Inference engine not initialized. Please upload a point cloud first.")
    
    try:
        # Run inference
        segmentation_result = await inference_service.run_inference(request)
        # Store results in session
        session.segmentation_result = segmentation_result
        
        # Prepare response
        segmentation = segmentation_result.mask.tolist()
        
        positive_points_count = len(segmentation) - segmentation.count(0)
        logger.info(f'Inference completed. Positive points in mask: {positive_points_count}')
        
        # Return with camelCase keys for frontend compatibility
        response = InferenceResponse(
            message="Inference completed successfully",
            segmented_point_cloud={
                "segmentation": segmentation,
                "object_counts": segmentation_result.object_counts,
                "metadata": segmentation_result.metadata
            }
        )
        return JSONResponse(content=response.model_dump(by_alias=True))
        
    except ValueError as e:
        logger.error(f"Validation error during inference: {str(e)}")
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error running inference: {str(e)}")
        raise HTTPException(500, f"Error running inference: {str(e)}")

@router.get("/status")
async def get_inference_status(
    inference_service: InferenceService = Depends(get_inference_service),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Get current inference status"""
    session = session_manager.get_current_session()
    inference_status = inference_service.get_inference_status()
    
    return {
        "inference_engine": inference_status,
        "session": {
            "has_point_cloud": session.point_cloud is not None,
            "has_results": session.segmentation_result is not None,
            "inference_initialized": session.inference_initialized
        }
    }
