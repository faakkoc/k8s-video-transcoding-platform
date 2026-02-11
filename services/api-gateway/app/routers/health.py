"""
Health check endpoints for monitoring and Kubernetes probes.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import datetime
from app.config import Settings, get_settings

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: datetime
    service: str
    version: str


class ReadinessResponse(BaseModel):
    """Readiness check response model."""
    ready: bool
    kubernetes_connected: bool
    timestamp: datetime


@router.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_settings)):
    """
    Basic health check endpoint.

    Used by Kubernetes liveness probe to check if the container is alive.
    This endpoint should always return 200 if the application is running.

    Returns:
        HealthResponse: Service status information
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        service=settings.app_name,
        version=settings.app_version
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check(settings: Settings = Depends(get_settings)):
    """
    Readiness check endpoint.

    Used by Kubernetes readiness probe to check if the service is ready
    to accept traffic. Checks external dependencies like Kubernetes API.

    Returns:
        ReadinessResponse: Readiness status with dependency checks
    """
    # TODO: Add actual Kubernetes API connectivity check
    kubernetes_connected = True

    return ReadinessResponse(
        ready=kubernetes_connected,
        kubernetes_connected=kubernetes_connected,
        timestamp=datetime.utcnow()
    )
