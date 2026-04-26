#!/usr/bin/env python3
"""
Transcoding Worker for Kubernetes Jobs

This worker processes video transcoding jobs created by the API Gateway.
Downloads input from Object Storage, transcodes with FFmpeg, uploads output.

Supports multiple storage backends via STORAGE_PROVIDER env var:
- "gcs": Google Cloud Storage via Workload Identity (GKE, no credentials needed)
- "s3":  S3-compatible via boto3 (MinIO local, StackIT production)

Environment Variables:
    STORAGE_PROVIDER: "gcs" or "s3" (default: "s3")
    INPUT_BUCKET: Storage bucket for input files
    OUTPUT_BUCKET: Storage bucket for output files
    INPUT_KEY: Input file key
    OUTPUT_KEY: Output file key
    PRESET: Transcoding quality preset
    JOB_ID: Kubernetes Job ID

    For S3 provider only:
        S3_ENDPOINT: S3-compatible endpoint URL
        S3_ACCESS_KEY: Access key
        S3_SECRET_KEY: Secret key

Date: 26.04.2026
"""

import os
import sys
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ffmpeg_presets import get_preset, get_available_presets


# ---------------------------------------------------------------------------
# Storage Abstraction
# ---------------------------------------------------------------------------

class StorageBackend(ABC):
    """Abstract storage backend interface."""

    @abstractmethod
    def download_file(self, bucket: str, key: str, local_path: str) -> bool:
        """Download file from storage to local path."""

    @abstractmethod
    def upload_file(self, local_path: str, bucket: str, key: str) -> bool:
        """Upload local file to storage."""


class GCSBackend(StorageBackend):
    """
    Google Cloud Storage via Workload Identity.
    No credentials needed — GKE handles authentication automatically.
    """

    def __init__(self):
        from google.cloud import storage
        self.client = storage.Client()
        print("[INIT] Storage: GCS via Workload Identity")

    def download_file(self, bucket: str, key: str, local_path: str) -> bool:
        try:
            self.client.bucket(bucket).blob(key).download_to_filename(local_path)
            return True
        except Exception as e:
            print(f"[ERROR] GCS download failed: {e}")
            return False

    def upload_file(self, local_path: str, bucket: str, key: str) -> bool:
        try:
            self.client.bucket(bucket).blob(key).upload_from_filename(local_path)
            return True
        except Exception as e:
            print(f"[ERROR] GCS upload failed: {e}")
            return False


class S3Backend(StorageBackend):
    """
    S3-compatible storage via boto3.
    Works with MinIO (local) and StackIT Object Storage.
    """

    def __init__(self):
        import boto3
        from botocore.client import Config

        endpoint = os.getenv("S3_ENDPOINT", "http://minio:9000")
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.getenv("S3_ACCESS_KEY", "minioadmin"),
            aws_secret_access_key=os.getenv("S3_SECRET_KEY", "minioadmin123"),
            region_name=os.getenv("S3_REGION", "us-east-1"),
            config=Config(signature_version="s3v4"),
        )
        print(f"[INIT] Storage: S3-compatible ({endpoint})")

    def download_file(self, bucket: str, key: str, local_path: str) -> bool:
        try:
            self.client.download_file(bucket, key, local_path)
            return True
        except Exception as e:
            print(f"[ERROR] S3 download failed: {e}")
            return False

    def upload_file(self, local_path: str, bucket: str, key: str) -> bool:
        try:
            self.client.upload_file(local_path, bucket, key)
            return True
        except Exception as e:
            print(f"[ERROR] S3 upload failed: {e}")
            return False


def get_storage_backend() -> StorageBackend:
    """Factory: returns GCS or S3 backend based on STORAGE_PROVIDER env var."""
    provider = os.getenv("STORAGE_PROVIDER", "s3")
    if provider == "gcs":
        return GCSBackend()
    return S3Backend()


# ---------------------------------------------------------------------------
# Transcoding Worker
# ---------------------------------------------------------------------------

class TranscodingWorker:
    """
    Video transcoding worker using FFmpeg and pluggable Object Storage.

    Workflow:
    1. Download input from Object Storage
    2. Transcode with FFmpeg
    3. Upload output to Object Storage
    4. Cleanup local files
    """

    def __init__(
            self,
            input_bucket: str,
            output_bucket: str,
            input_key: str,
            output_key: str,
            preset_name: str,
            job_id: str,
    ):
        self.job_id = job_id
        self.preset_name = preset_name
        self.input_bucket = input_bucket
        self.output_bucket = output_bucket
        self.input_key = input_key
        self.output_key = output_key

        self.input_path = Path("/tmp") / input_key
        self.output_path = Path("/tmp") / output_key

        self.storage = get_storage_backend()

        try:
            self.preset = get_preset(preset_name)
        except ValueError as e:
            print(f"[ERROR] Invalid preset: {e}")
            sys.exit(1)

        print("[INIT] Transcoding Worker")
        print(f"   Job ID: {self.job_id}")
        print(f"   Preset: {self.preset_name}")
        print(f"   Input: {input_bucket}/{input_key}")
        print(f"   Output: {output_bucket}/{output_key}")

    def download_input(self) -> bool:
        print("[START] Downloading input...")
        try:
            self.input_path.parent.mkdir(parents=True, exist_ok=True)
            success = self.storage.download_file(
                self.input_bucket, self.input_key, str(self.input_path)
            )
            if not success or not self.input_path.exists():
                print("[ERROR] Download failed")
                return False
            file_size_mb = self.input_path.stat().st_size / (1024 * 1024)
            print(f"[OK] Downloaded {file_size_mb:.2f} MB")
            return True
        except Exception as e:
            print(f"[ERROR] Unexpected error during download: {e}")
            return False

    def run_ffmpeg(self) -> bool:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        ffmpeg_args = ["ffmpeg", "-i", str(self.input_path), "-y"]
        ffmpeg_args.extend(self.preset.to_ffmpeg_args())
        ffmpeg_args.append(str(self.output_path))

        print("[START] Starting FFmpeg transcoding...")
        print(f"   Command: {' '.join(ffmpeg_args)}")

        start_time = time.time()
        try:
            subprocess.run(
                ffmpeg_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            elapsed = time.time() - start_time
            print(f"[OK] Transcoding completed in {elapsed:.1f} seconds")
            return True
        except subprocess.CalledProcessError as e:
            elapsed = time.time() - start_time
            print(f"[ERROR] FFmpeg failed after {elapsed:.1f} seconds")
            print(f"   Exit code: {e.returncode}")
            print(f"   Stderr (last 500 chars): {e.stderr[-500:]}")
            return False
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            return False

    def upload_output(self) -> bool:
        print("[START] Uploading output...")
        try:
            if not self.output_path.exists():
                print(f"[ERROR] Output file not found: {self.output_path}")
                return False

            file_size_mb = self.output_path.stat().st_size / (1024 * 1024)
            if file_size_mb == 0:
                print("[ERROR] Output file is empty")
                return False

            success = self.storage.upload_file(
                str(self.output_path), self.output_bucket, self.output_key
            )
            if not success:
                return False

            print(f"[OK] Uploaded {file_size_mb:.2f} MB to {self.output_bucket}/{self.output_key}")
            return True
        except Exception as e:
            print(f"[ERROR] Unexpected error during upload: {e}")
            return False

    def cleanup(self):
        print("[CLEANUP] Removing temporary files...")
        for path in [self.input_path, self.output_path]:
            try:
                if path.exists():
                    path.unlink()
                    print(f"   Deleted: {path}")
            except Exception as e:
                print(f"   Failed to delete {path}: {e}")

    def run(self) -> int:
        print(f"\n{'='*60}")
        print(f"TRANSCODING JOB: {self.job_id}")
        print(f"{'='*60}\n")

        try:
            if not self.download_input():
                return 1
            if not self.run_ffmpeg():
                self.cleanup()
                return 1
            if not self.upload_output():
                self.cleanup()
                return 1
            self.cleanup()
            print(f"\n{'='*60}")
            print(f"JOB COMPLETED SUCCESSFULLY: {self.job_id}")
            print(f"{'='*60}\n")
            return 0
        except Exception as e:
            print(f"[ERROR] Unexpected error in workflow: {e}")
            self.cleanup()
            return 1


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    """Main entry point — reads config from environment variables."""
    provider = os.getenv("STORAGE_PROVIDER", "s3")

    required_vars = {
        "INPUT_BUCKET":  os.getenv("INPUT_BUCKET"),
        "OUTPUT_BUCKET": os.getenv("OUTPUT_BUCKET"),
        "INPUT_KEY":     os.getenv("INPUT_KEY"),
        "OUTPUT_KEY":    os.getenv("OUTPUT_KEY"),
        "PRESET":        os.getenv("PRESET"),
        "JOB_ID":        os.getenv("JOB_ID"),
    }

    # S3 credentials only required for S3 provider
    if provider == "s3":
        required_vars["S3_ENDPOINT"]   = os.getenv("S3_ENDPOINT")
        required_vars["S3_ACCESS_KEY"] = os.getenv("S3_ACCESS_KEY")
        required_vars["S3_SECRET_KEY"] = os.getenv("S3_SECRET_KEY")

    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        print("[ERROR] Missing required environment variables:")
        for var in missing:
            print(f"   {var}: MISSING")
        print(f"\nAvailable presets: {', '.join(get_available_presets())}")
        sys.exit(1)

    worker = TranscodingWorker(
        input_bucket=required_vars["INPUT_BUCKET"],
        output_bucket=required_vars["OUTPUT_BUCKET"],
        input_key=required_vars["INPUT_KEY"],
        output_key=required_vars["OUTPUT_KEY"],
        preset_name=required_vars["PRESET"],
        job_id=required_vars["JOB_ID"],
    )

    sys.exit(worker.run())


if __name__ == "__main__":
    main()