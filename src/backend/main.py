from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import upload, inference, recognition, download
from container import Container
from config.settings import settings
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting AGILE3D Interactive Segmentation API v2.0.0")
    logger.info(f"Settings: {settings.dict()}")
    yield
    # Shutdown
    logger.info("Shutting down AGILE3D API")

def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    
    # Create container
    container = Container()
    
    # Create FastAPI app
    app = FastAPI(
        title="AGILE3D Interactive Segmentation API",
        version="2.0.0",
        description="Refactored backend for interactive 3D point cloud segmentation",
        debug=settings.debug,
        lifespan=lifespan
    )
    
    # Set up container
    app.container = container
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
    
    # Include routers
    app.include_router(upload.router, prefix="/api")
    app.include_router(inference.router, prefix="/api")
    app.include_router(recognition.router, prefix="/api")
    app.include_router(download.router, prefix="/api")
    
    # Mount static files
    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "version": "2.0.0",
            "message": "AGILE3D API is running"
        }
    
    return app

# Create the app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {settings.host}:{settings.port}")
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
