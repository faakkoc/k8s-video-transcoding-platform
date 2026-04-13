"""
S3 Client for Object Storage.

Works with:
- MinIO (local development)
- GCP Cloud Storage (production)
- StackIT Object Storage (production)
"""

import os
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from typing import BinaryIO, Optional
import logging

logger = logging.getLogger(__name__)


class S3Client:
    """S3-compatible storage client."""

    def __init__(self):
        """Initialize S3 client from environment variables."""
        self.endpoint_url = os.getenv("S3_ENDPOINT", "http://minio:9000")
        self.access_key = os.getenv("S3_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("S3_SECRET_KEY", "minioadmin123")
        self.region = os.getenv("S3_REGION", "us-east-1")

        # Initialize boto3 client
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=Config(signature_version='s3v4')
        )

        logger.info(f"[INIT] S3 Client initialized: {self.endpoint_url}")

    def upload_file(
            self,
            file_obj: BinaryIO,
            bucket: str,
            key: str
    ) -> bool:
        """
        Upload file to S3 bucket.

        Args:
            file_obj: File-like object to upload
            bucket: S3 bucket name
            key: Object key (filename in bucket)

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.upload_fileobj(file_obj, bucket, key)
            logger.info(f"[OK] Uploaded to s3://{bucket}/{key}")
            return True
        except ClientError as e:
            logger.error(f"[ERROR] Upload failed: {e}")
            return False

    def download_file(
            self,
            bucket: str,
            key: str,
            local_path: str
    ) -> bool:
        """
        Download file from S3 bucket.

        Args:
            bucket: S3 bucket name
            key: Object key (filename in bucket)
            local_path: Local path to save file

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.download_file(bucket, key, local_path)
            logger.info(f"[OK] Downloaded s3://{bucket}/{key} to {local_path}")
            return True
        except ClientError as e:
            logger.error(f"[ERROR] Download failed: {e}")
            return False

    def file_exists(self, bucket: str, key: str) -> bool:
        """
        Check if file exists in S3 bucket.

        Args:
            bucket: S3 bucket name
            key: Object key (filename)

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False

    def get_file_url(
            self,
            bucket: str,
            key: str,
            expiration: int = 3600
    ) -> Optional[str]:
        """
        Generate pre-signed URL for file download.

        Args:
            bucket: S3 bucket name
            key: Object key (filename)
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Pre-signed URL or None if error
        """
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiration
            )
            logger.info(f"[OK] Generated presigned URL for s3://{bucket}/{key}")
            return url
        except ClientError as e:
            logger.error(f"[ERROR] URL generation failed: {e}")
            return None

    def delete_file(self, bucket: str, key: str) -> bool:
        """
        Delete file from S3 bucket.

        Args:
            bucket: S3 bucket name
            key: Object key (filename)

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.delete_object(Bucket=bucket, Key=key)
            logger.info(f"[OK] Deleted s3://{bucket}/{key}")
            return True
        except ClientError as e:
            logger.error(f"[ERROR] Delete failed: {e}")
            return False


# Singleton instance
_s3_client: Optional[S3Client] = None


def get_s3_client() -> S3Client:
    """
    Get or create S3 client singleton.

    Returns:
        S3Client instance
    """
    global _s3_client
    if _s3_client is None:
        _s3_client = S3Client()
    return _s3_client