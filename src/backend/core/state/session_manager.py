import uuid
from typing import Dict, Optional
from core.models.domain import SessionState, PointCloudData, SegmentationResult, ObjectInfo
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

class SessionManager:
    """Manages session state for the application"""
    
    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._current_session_id: Optional[str] = None
    
    def create_session(self) -> str:
        """Create a new session and return its ID"""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = SessionState(session_id=session_id)
        self._current_session_id = session_id
        logger.info(f"Created new session: {session_id}")
        return session_id
    
    def get_current_session(self) -> SessionState:
        """Get the current session, creating one if none exists"""
        if not self._current_session_id or self._current_session_id not in self._sessions:
            self.create_session()
        return self._sessions[self._current_session_id]
    
    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get a specific session by ID"""
        return self._sessions.get(session_id)
    
    def set_current_session(self, session_id: str) -> bool:
        """Set the current session ID"""
        if session_id in self._sessions:
            self._current_session_id = session_id
            logger.info(f"Switched to session: {session_id}")
            return True
        return False
    
    def clear_session(self, session_id: str) -> bool:
        """Clear all data from a session"""
        session = self.get_session(session_id)
        if session:
            session.clear_all()
            logger.info(f"Cleared session: {session_id}")
            return True
        return False
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session completely"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            if self._current_session_id == session_id:
                self._current_session_id = None
            logger.info(f"Deleted session: {session_id}")
            return True
        return False
    
    def list_sessions(self) -> Dict[str, Dict[str, any]]:
        """List all sessions with basic info"""
        return {
            session_id: {
                "has_point_cloud": session.point_cloud is not None,
                "has_results": session.segmentation_result is not None,
                "object_count": len(session.object_info),
                "inference_initialized": session.inference_initialized
            }
            for session_id, session in self._sessions.items()
        }

# Global session manager instance
# In a production environment, you might want to use Redis or database for persistence
session_manager = SessionManager()
