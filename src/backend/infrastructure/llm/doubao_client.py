import base64
import io
import json
import os
from typing import List, Dict, Any, Optional
from PIL import Image

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    httpx = None  # type: ignore

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from infrastructure.llm.base import LLMClient
from infrastructure.logging.logger import get_logger

from dotenv import load_dotenv
load_dotenv()


logger = get_logger(__name__)


class DoubaoClient(LLMClient):
    """Doubao (Volcengine Ark) client via OpenAI-compatible SDK.

    - Uses OpenAI Python SDK with a custom base_url to call Ark endpoints
    - Supports multimodal chat.completions with inline data URLs for images
    - Returns a structured JSON object aligned with internal expectations
    - Extensible to any OpenAI-compatible model by passing different model IDs
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = 'doubao-seed-1-6-vision-250815',
        timeout: int = 20000,
        max_retries: int = 3,
        input_price_per_million: Optional[float] = None,
        output_price_per_million: Optional[float] = None,
    ):
        self.api_key = api_key or os.environ.get("ARK_API_KEY")
        self.base_url = base_url or os.environ.get(
            "ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
        )
        # Allow model to be provided via constructor or env var for extensibility
        self.model = model or os.environ.get("ARK_MODEL_ID")
        self.timeout = timeout
        self.max_retries = max_retries

        # Pricing is model-dependent and often changes; allow env overrides
        # Default to 0 if not provided so cost accounting is opt-in
        self.input_price_per_million = (
            input_price_per_million
            if input_price_per_million is not None
            else self._read_float_env("ARK_INPUT_PRICE_PER_1M")
        )
        self.output_price_per_million = (
            output_price_per_million
            if output_price_per_million is not None
            else self._read_float_env("ARK_OUTPUT_PRICE_PER_1M")
        )

        if OpenAI is None:
            logger.warning(
                "OpenAI SDK not installed. Doubao client will be unavailable."
            )
            self.client = None
            return

        if not self.api_key:
            logger.warning(
                "No ARK_API_KEY provided. Doubao client will be unavailable."
            )
            self.client = None
            return

        try:
            # The OpenAI client supports base_url for OpenAI-compatible providers
            # timeout is in seconds for the SDK; convert ms -> s
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout / 1000.0,
            )
            logger.info("Doubao (Ark) client initialized successfully")
        except Exception as e:  # pragma: no cover - network/env dependent
            logger.error(f"Failed to initialize Doubao client: {e}")
            self.client = None

    def _read_float_env(self, key: str) -> Optional[float]:
        value = os.environ.get(key)
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            logger.warning(f"Invalid float for env {key}: {value}")
            return None

    def _image_to_data_url(self, image: Image.Image) -> str:
        """Convert PIL image to a data URL suitable for OpenAI-compatible image_url."""
        buffered = io.BytesIO()
        # Prefer JPEG for size; fall back to PNG if necessary
        mode = image.mode
        save_format = "JPEG" if mode in {"RGB", "L"} else "PNG"
        if save_format == "JPEG" and mode != "RGB":
            image = image.convert("RGB")
        image.save(buffered, format=save_format)
        encoded = base64.b64encode(buffered.getvalue()).decode("utf-8")
        mime = "image/jpeg" if save_format == "JPEG" else "image/png"
        return f"data:{mime};base64,{encoded}"

    def _build_messages(self, images: List[Image.Image], prompt: str) -> List[Dict[str, Any]]:
        user_content: List[Dict[str, Any]] = []
        for img in images:
            data_url = self._image_to_data_url(img)
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                }
            )
        user_content.append({"type": "text", "text": prompt})

        system_prompt = (
            "You are a vision assistant. Return ONLY a JSON object with keys: "
            "selected_views (array of integers), description (string), label (string). "
            "Do not include any additional commentary."
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    async def analyze_images(self, images: List[Image.Image], prompt: str) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("Doubao client not available")

        if not self.model:
            raise RuntimeError(
                "No model configured. Pass model=... or set ARK_MODEL_ID env var."
            )

        messages = self._build_messages(images, prompt)

        last_err: Optional[Exception] = None
        response = None
        for i in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0,
                )
                break
            except Exception as e:  # pragma: no cover - network dependent
                last_err = e
                # Distinguish timeout if httpx is available
                if httpx and isinstance(e, (httpx.ReadTimeout, httpx.ConnectTimeout)):
                    logger.warning(
                        f"Doubao request timed out, retry {i + 1}/{self.max_retries}"
                    )
                else:
                    logger.warning(
                        f"Doubao request failed, retry {i + 1}/{self.max_retries}: {e}"
                    )
                if i == self.max_retries - 1:
                    raise e

        if response is None:
            raise RuntimeError(
                f"Failed to get response from Doubao after {self.max_retries} retries"
            )

        try:
            text = response.choices[0].message.content  # type: ignore[attr-defined]
        except Exception as e:  # pragma: no cover
            logger.error(f"Unexpected Doubao response format: {e}")
            raise

        try:
            result = json.loads(text)
        except Exception:
            # Best-effort fallback: wrap raw text into expected schema
            logger.warning("Model did not return valid JSON; wrapping raw text")
            result = {
                "selected_views": [],
                "description": text,
                "label": "",
            }

        result["cost"] = self.get_cost(response)
        return result

    def get_cost(self, response: Any) -> float:
        try:
            usage = getattr(response, "usage", None)
            if usage is None:
                # Some SDK versions use dict-like access
                usage = response.get("usage") if isinstance(response, dict) else None
            if usage is None:
                return 0.0

            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)
            if prompt_tokens is None or completion_tokens is None:
                # dict-like
                prompt_tokens = (
                    usage.get("prompt_tokens") if isinstance(usage, dict) else 0
                )
                completion_tokens = (
                    usage.get("completion_tokens") if isinstance(usage, dict) else 0
                )

            input_price = self.input_price_per_million or 0.0
            output_price = self.output_price_per_million or 0.0
            cost = (float(prompt_tokens) / 1e6) * input_price + (
                float(completion_tokens) / 1e6
            ) * output_price
            return float(cost)
        except Exception as e:
            logger.warning(f"Failed to calculate cost: {e}")
            return 0.0


