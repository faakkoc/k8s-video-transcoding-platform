"""
Configuration management for API Gateway.
Uses Pydantic Settings to load configuration from environment variables.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    In Kubernetes, these will be set via ConfigMaps and Secrets.
    For local development, create a .env file.
    """

    # Application
    app_name: str = "Video Transcoding API Gateway"
    app_version: str = "0.1.0"
    debug: bool = False

    # API Configuration
    api_prefix: str = "/api/v1"
    max_upload_size_mb: int = 500  # Maximum video file size in MB

    # Kubernetes Configuration
    kubernetes_namespace: str = "video-transcoding"
    in_cluster: bool = True  # Set to False for local development

    # Storage Configuration (Future: MinIO or S3)
    storage_type: str = "filesystem"  # Options: filesystem, s3, minio
    upload_dir: str = "/tmp/uploads"
    output_dir: str = "/tmp/outputs"

    # Job Configuration
    transcoding_worker_image: str = "transcoding-worker:latest"
    job_ttl_seconds: int = 86400  # Clean up jobs after 24 hours

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached settings instance.
    Using lru_cache ensures settings are loaded only once.
    """
    return Settings()
