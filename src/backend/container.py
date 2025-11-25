from core.services.point_cloud_service import PointCloudService
from core.services.inference_service import InferenceService
from core.services.recognition_service import RecognitionService
from core.services.export_service import ExportService
from core.state.session_manager import SessionManager, session_manager
from infrastructure.storage.local_storage import LocalStorageService
from infrastructure.rendering.view_renderer import ViewRenderer
from infrastructure.llm.doubao_client import DoubaoClient
from config.settings import settings

class Container:
    """Simple dependency injection container"""
    
    def __init__(self):
        # Initialize infrastructure components
        self._storage_service = LocalStorageService(
            upload_dir=settings.upload_dir,
            output_dir=settings.output_dir
        )
        
        self._view_renderer = ViewRenderer()
        
        # Initialize LLM client
        self._llm_client = DoubaoClient(
            api_key=settings.ark_api_key,
            timeout=settings.llm_timeout,
            max_retries=settings.llm_max_retries
        )
        
        # Initialize session manager (using singleton)
        self._session_manager = session_manager
        
        # Services will be created on demand
        self._point_cloud_service = None
        self._inference_service = None
        self._recognition_service = None
        self._export_service = None
    
    def point_cloud_service(self) -> PointCloudService:
        """Get or create point cloud service"""
        if self._point_cloud_service is None:
            self._point_cloud_service = PointCloudService(
                storage_service=self._storage_service
            )
        return self._point_cloud_service
    
    def inference_service(self) -> InferenceService:
        """Get or create inference service"""
        if self._inference_service is None:
            self._inference_service = InferenceService(
                model_weights_path=settings.model_weights_path,
                voxel_size=settings.voxel_size
            )
        return self._inference_service
    
    def recognition_service(self) -> RecognitionService:
        """Get or create recognition service"""
        if self._recognition_service is None:
            self._recognition_service = RecognitionService(
                llm_client=self._llm_client,
                view_renderer=self._view_renderer,
                max_workers=settings.max_workers
            )
        return self._recognition_service
    
    def export_service(self) -> ExportService:
        """Get or create export service"""
        if self._export_service is None:
            self._export_service = ExportService(
                storage_service=self._storage_service
            )
        return self._export_service
    
    def session_manager(self) -> SessionManager:
        """Get session manager"""
        return self._session_manager
    
    def storage_service(self) -> LocalStorageService:
        """Get storage service"""
        return self._storage_service
    
    def view_renderer(self) -> ViewRenderer:
        """Get view renderer"""
        return self._view_renderer
