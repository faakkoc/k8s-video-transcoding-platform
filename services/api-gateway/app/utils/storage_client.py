"""
Storage Client Abstraction

Supports multiple storage backends:
- GCS (Google Cloud Storage) via Workload Identity — no credentials needed
- S3-compatible (MinIO, StackIT) via boto3 + HMAC Keys

Usage:
    from app.utils.storage_client import get_storage_client

    client = get_storage_client()
    client.upload_file(file_obj, bucket, key)

Environment Variables:
    STORAGE_PROVIDER: "gcs" or "s3" (default: "s3")

    For S3 provider only:
        S3_ENDPOINT: S3-compatible endpoint URL
        S3_ACCESS_KEY: Access key
        S3_SECRET_KEY: Secret key
        S3_REGION: Region (default: "us-east-1")
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional

logger = logging.getLogger(__name__)


class StorageClient(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def upload_file(self, file_obj: BinaryIO, bucket: str, key: str) -> bool:
        """Upload file to storage bucket."""

    @abstractmethod
    def download_file(self, bucket: str, key: str, local_path: str) -> bool:
        """Download file from storage bucket."""

    @abstractmethod
    def file_exists(self, bucket: str, key: str) -> bool:
        """Check if file exists in storage bucket."""

    @abstractmethod
    def get_file_url(self, bucket: str, key: str, expiration: int = 3600) -> Optional[str]:
        """Generate pre-signed/signed URL for file download."""

    @abstractmethod
    def delete_file(self, bucket: str, key: str) -> bool:
        """Delete file from storage bucket."""


class GCSClient(StorageClient):
    """
    Google Cloud Storage client using Workload Identity.

    No credentials needed — authentication is handled automatically
    by GKE Workload Identity via the pod's Kubernetes ServiceAccount.
    """

    def __init__(self):
        from google.cloud import storage
        self.client = storage.Client()
        logger.info("[INIT] GCS Client initialized via Workload Identity")

    def upload_file(self, file_obj: BinaryIO, bucket: str, key: str) -> bool:
        try:
            blob = self.client.bucket(bucket).blob(key)
            blob.upload_from_file(file_obj)
            logger.info(f"[OK] Uploaded to gs://{bucket}/{key}")
            return True
        except Exception as e:
            logger.error(f"[ERROR] GCS upload failed: {e}")
            return False

    def download_file(self, bucket: str, key: str, local_path: str) -> bool:
        try:
            blob = self.client.bucket(bucket).blob(key)
            blob.download_to_filename(local_path)
            logger.info(f"[OK] Downloaded gs://{bucket}/{key} to {local_path}")
            return True
        except Exception as e:
            logger.error(f"[ERROR] GCS download failed: {e}")
            return False

    def file_exists(self, bucket: str, key: str) -> bool:
        try:
            return self.client.bucket(bucket).blob(key).exists()
        except Exception:
            return False

    def get_file_url(self, bucket: str, key: str, expiration: int = 3600) -> Optional[str]:
        try:
            from datetime import timedelta
            blob = self.client.bucket(bucket).blob(key)
            url = blob.generate_signed_url(
                expiration=timedelta(seconds=expiration),
                method="GET",
                version="v4"
            )
            logger.info(f"[OK] Generated signed URL for gs://{bucket}/{key}")
            return url
        except Exception as e:
            logger.error(f"[ERROR] GCS URL generation failed: {e}")
            return None

    def delete_file(self, bucket: str, key: str) -> bool:
        try:
            self.client.bucket(bucket).blob(key).delete()
            logger.info(f"[OK] Deleted gs://{bucket}/{key}")
            return True
        except Exception as e:
            logger.error(f"[ERROR] GCS delete failed: {e}")
            return False


class S3Client(StorageClient):
    """
    S3-compatible storage client using boto3.

    Works with MinIO (local) and StackIT Object Storage (production).
    Requires S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY environment variables.
    """

    def __init__(self):
        import boto3
        from botocore.client import Config

        endpoint_url = os.getenv("S3_ENDPOINT", "http://minio:9000")
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=os.getenv("S3_ACCESS_KEY", "minioadmin"),
            aws_secret_access_key=os.getenv("S3_SECRET_KEY", "minioadmin123"),
            region_name=os.getenv("S3_REGION", "us-east-1"),
            config=Config(signature_version="s3v4"),
        )
        logger.info(f"[INIT] S3 Client initialized: {endpoint_url}")

    def upload_file(self, file_obj: BinaryIO, bucket: str, key: str) -> bool:
        try:
            from botocore.exceptions import ClientError
            self.client.upload_fileobj(file_obj, bucket, key)
            logger.info(f"[OK] Uploaded to s3://{bucket}/{key}")
            return True
        except Exception as e:
            logger.error(f"[ERROR] S3 upload failed: {e}")
            return False

    def download_file(self, bucket: str, key: str, local_path: str) -> bool:
        try:
            self.client.download_file(bucket, key, local_path)
            logger.info(f"[OK] Downloaded s3://{bucket}/{key} to {local_path}")
            return True
        except Exception as e:
            logger.error(f"[ERROR] S3 download failed: {e}")
            return False

    def file_exists(self, bucket: str, key: str) -> bool:
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False

    def get_file_url(self, bucket: str, key: str, expiration: int = 3600) -> Optional[str]:
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expiration,
            )
            logger.info(f"[OK] Generated presigned URL for s3://{bucket}/{key}")
            return url
        except Exception as e:
            logger.error(f"[ERROR] S3 URL generation failed: {e}")
            return None

    def delete_file(self, bucket: str, key: str) -> bool:
        try:
            self.client.delete_object(Bucket=bucket, Key=key)
            logger.info(f"[OK] Deleted s3://{bucket}/{key}")
            return True
        except Exception as e:
            logger.error(f"[ERROR] S3 delete failed: {e}")
            return False


# Singleton instance
_storage_client: Optional[StorageClient] = None


def get_storage_client() -> StorageClient:
    """
    Get or create storage client singleton.

    Reads STORAGE_PROVIDER environment variable:
    - "gcs": Google Cloud Storage via Workload Identity (GKE)
    - "s3":  S3-compatible via boto3 (MinIO, StackIT) — default

    Returns:
        StorageClient instance
    """
    global _storage_client
    if _storage_client is None:
        provider = os.getenv("STORAGE_PROVIDER", "s3")
        if provider == "gcs":
            _storage_client = GCSClient()
        else:
            _storage_client = S3Client()
    return _storage_client
