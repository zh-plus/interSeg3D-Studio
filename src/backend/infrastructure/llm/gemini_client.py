import json
import os
from typing import List, Dict, Any
from PIL import Image

try:
    import httpx
    from google import genai
    from google.genai import types
except ImportError:
    httpx = None
    genai = None
    types = None

from infrastructure.llm.base import LLMClient
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

class GeminiClient(LLMClient):
    """Google Gemini LLM client implementation"""
    
    def __init__(self, api_key: str, timeout: int = 20000, max_retries: int = 3):
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        
        if not genai:
            logger.warning("Google GenAI not installed. Object recognition will not work.")
            self.client = None
            return
            
        if not api_key:
            logger.warning("No Google API key provided. Object recognition will not work.")
            self.client = None
            return
            
        try:
            self.client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=timeout)
            )
            logger.info("Gemini client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.client = None
    
    async def analyze_images(self, images: List[Image.Image], prompt: str) -> Dict[str, Any]:
        """Analyze images with a text prompt and return structured response"""
        if not self.client:
            raise RuntimeError("Gemini client not available")
        
        response = None
        for i in range(self.max_retries):
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=images + [prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type='application/json',
                        response_schema={
                            "type": "object",
                            "properties": {
                                "selected_views": {"type": "array", "items": {"type": "integer"}},
                                "description": {"type": "string"},
                                "label": {"type": "string"}
                            },
                            "required": ["selected_views", "description", "label"]
                        }
                    )
                )
                break
            except (httpx.ConnectTimeout, httpx.ReadTimeout) if httpx else Exception as e:
                logger.warning(f"Request timed out, retry {i + 1}/{self.max_retries}")
                if i == self.max_retries - 1:
                    raise e
        
        if response is None:
            raise RuntimeError("Failed to get response from Gemini after retries")
        
        result = json.loads(response.text)
        result['cost'] = self.get_cost(response)
        
        return result
    
    def get_cost(self, response) -> float:
        """Calculate the cost of an API call"""
        try:
            # per 1M tokens in USD
            input_price = 0.1
            output_price = 0.4
            
            prompt_token = response.usage_metadata.prompt_token_count
            output_token = response.usage_metadata.candidates_token_count
            
            cost = (prompt_token + output_token) / 1e6 * (input_price + output_price)
            return cost
        except Exception as e:
            logger.warning(f"Failed to calculate cost: {e}")
            return 0.0
