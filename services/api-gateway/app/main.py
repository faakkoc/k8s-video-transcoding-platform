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
from app.routers import health, upload, jobs

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

# CORS Configuration (Swagger UI / programmatic access)
# allow_credentials=False, weil allow_origins=["*"] + allow_credentials=True
# laut CORS-Spezifikation ungültig ist (Browser lehnen das ab). Es werden
# keine Cookies/Auth-Header genutzt, daher werden Credentials nicht benötigt.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(upload.router, prefix=settings.api_prefix)
app.include_router(jobs.router, prefix=settings.api_prefix)


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

    Logs the effective multi-cloud configuration (STORAGE_PROVIDER,
    K8S_NAMESPACE) for debugging — these come from the environment
    (ConfigMap), not from Settings, see app/config.py.
    """
    import os

    storage_provider = os.getenv("STORAGE_PROVIDER", "s3")
    namespace = os.getenv("K8S_NAMESPACE", "video-transcoding")

    print(f"[START] {settings.app_name} v{settings.app_version} started")
    print(f"[CONFIG] Storage provider: {storage_provider}")
    print(f"[CONFIG] Kubernetes namespace: {namespace}")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Runs on application shutdown.
    Clean up resources, close connections, etc.
    """
    print(f"[SHUTDOWN] {settings.app_name} shutting down")