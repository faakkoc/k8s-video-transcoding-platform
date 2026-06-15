"""
Configuration management for API Gateway.
Uses Pydantic Settings to load configuration from environment variables.

Note: Kubernetes- und Storage-spezifische Konfiguration (STORAGE_PROVIDER,
S3_*, K8S_NAMESPACE, TRANSCODING_WORKER_IMAGE, IMAGE_PULL_SECRET/POLICY,
INPUT_BUCKET, OUTPUT_BUCKET) wird direkt via os.getenv() in k8s_client.py
und storage_client.py gelesen, nicht über Settings — diese Werte werden
pro Cloud/Job benötigt und ändern sich nicht zur Laufzeit.
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

    # API Configuration
    api_prefix: str = "/api/v1"
    max_upload_size_mb: int = 500  # Maximum video file size in MB

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