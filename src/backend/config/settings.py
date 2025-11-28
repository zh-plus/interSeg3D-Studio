from pydantic_settings import BaseSettings
from pathlib import Path
import os

class Settings(BaseSettings):
    # API settings
    host: str = "0.0.0.0"
    port: int = 9502
    debug: bool = False

    # Proxy settings
    http_proxy: str = ""
    https_proxy: str = ""
    
    # Model settings
    CONFIG_DIR = Path(__file__).resolve().parent
    BACKEND_DIR = CONFIG_DIR.parent   # src/backend
    PINPOINT3D_DIR = BACKEND_DIR / "pinpoint3d"
    model_weights_path: str = str(PINPOINT3D_DIR / "weights" / "checkpoint1099.pth")
    voxel_size: float = 0.05
    
    # Storage settings
    upload_dir: Path = Path("./uploads")
    output_dir: Path = Path("./outputs")
    static_dir: Path = Path("./static")
    temp_dir: Path = Path("./temp")
    
    # LLM settings
    ark_api_key: str = ""
    gemini_api_key: str = ""
    llm_timeout: int = 20000
    llm_max_retries: int = 3
    
    # Logging
    log_level: str = "INFO"
    log_dir: Path = Path("./logs")
    
    # CORS settings
    cors_origins: list = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list = ["*"]
    cors_allow_headers: list = ["*"]
    
    # File processing
    max_file_size: int = 500 * 1024 * 1024  # 100MB
    allowed_extensions: list = [".ply"]
    
    # Multiprocessing
    max_workers: int = 8
    
    class Config:
        env_file = ".env"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        for dir_path in [self.upload_dir, self.output_dir, self.static_dir, self.temp_dir, self.log_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

settings = Settings()
