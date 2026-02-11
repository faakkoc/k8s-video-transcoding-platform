"""
API Gateway for Video Transcoding Platform.

This service handles:
- Video file uploads
- Creation of Kubernetes Jobs for transcoding
- Status monitoring of transcoding jobs
- Download of processed videos
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import health

# Load settings
settings = get_settings()

# Initialize FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API Gateway for cloud-native video transcoding platform",
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

# CORS Configuration (for frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    """
    Root endpoint - API information.
    """
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": f"{settings.api_prefix}/docs",
        "health": f"{settings.api_prefix}/health",
    }


@app.on_event("startup")
async def startup_event():
    """
    Runs on application startup.
    Initialize connections, create directories, etc.
    """
    import os

    # Create upload and output directories if they don't exist
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.output_dir, exist_ok=True)

    print(f"🚀 {settings.app_name} v{settings.app_version} started")
    print(f"📁 Upload directory: {settings.upload_dir}")
    print(f"📁 Output directory: {settings.output_dir}")
    print(f"🔧 Kubernetes namespace: {settings.kubernetes_namespace}")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Runs on application shutdown.
    Clean up resources, close connections, etc.
    """
    print(f"👋 {settings.app_name} shutting down")
