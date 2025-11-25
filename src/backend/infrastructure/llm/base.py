from abc import ABC, abstractmethod
from typing import List, Dict, Any
from PIL import Image

class LLMClient(ABC):
    """Abstract base class for LLM clients"""
    
    @abstractmethod
    async def analyze_images(self, images: List[Image.Image], prompt: str) -> Dict[str, Any]:
        """Analyze images with a text prompt and return structured response"""
        pass
    
    @abstractmethod
    def get_cost(self, response: Any) -> float:
        """Calculate the cost of an API call"""
        pass
