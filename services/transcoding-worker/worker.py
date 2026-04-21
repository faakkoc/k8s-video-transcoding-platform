#!/usr/bin/env python3
"""
Transcoding Worker for Kubernetes Jobs

This worker processes video transcoding jobs created by the API Gateway.
Downloads input from MinIO, transcodes with FFmpeg, uploads output to MinIO.

Environment Variables:
    S3_ENDPOINT: MinIO endpoint URL
    S3_ACCESS_KEY: MinIO access key
    S3_SECRET_KEY: MinIO secret key
    INPUT_BUCKET: S3 bucket for input files
    OUTPUT_BUCKET: S3 bucket for output files
    INPUT_KEY: Input file S3 key
    OUTPUT_KEY: Output file S3 key
    PRESET: Transcoding quality preset
    JOB_ID: Kubernetes Job ID

Date: 09.04.2026
"""

import os
import sys
import subprocess
import time
import boto3
from pathlib import Path
from botocore.exceptions import ClientError

from ffmpeg_presets import get_preset, get_available_presets


class TranscodingWorker:
    """
    Video transcoding worker using FFmpeg and MinIO.

    Workflow:
    1. Download input from MinIO
    2. Transcode with FFmpeg
    3. Upload output to MinIO
    4. Cleanup local files
    """

    def __init__(
            self,
            s3_endpoint: str,
            s3_access_key: str,
            s3_secret_key: str,
            input_bucket: str,
            output_bucket: str,
            input_key: str,
            output_key: str,
            preset_name: str,
            job_id: str
    ):
        """Initialize transcoding worker."""
        self.job_id = job_id
        self.preset_name = preset_name

        # S3 configuration
        self.input_bucket = input_bucket
        self.output_bucket = output_bucket
        self.input_key = input_key
        self.output_key = output_key

        # Local file paths
        self.input_path = Path("/tmp") / input_key
        self.output_path = Path("/tmp") / output_key

        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            endpoint_url=s3_endpoint,
            aws_access_key_id=s3_access_key,
            aws_secret_access_key=s3_secret_key
        )

        # Load preset
        try:
            self.preset = get_preset(preset_name)
        except ValueError as e:
            print(f"[ERROR] Invalid preset: {e}")
            sys.exit(1)

        print("[INIT] Transcoding Worker")
        print(f"   Job ID: {self.job_id}")
        print(f"   Preset: {self.preset_name}")
        print(f"   S3 Endpoint: {s3_endpoint}")
        print(f"   Input: s3://{input_bucket}/{input_key}")
        print(f"   Output: s3://{output_bucket}/{output_key}")

    def download_input(self) -> bool:
        """
        Download input file from MinIO.

        Returns:
            True if successful, False otherwise
        """
        print("[START] Downloading input from MinIO...")

        try:
            # Ensure parent directory exists
            self.input_path.parent.mkdir(parents=True, exist_ok=True)

            # Download file
            self.s3_client.download_file(
                self.input_bucket,
                self.input_key,
                str(self.input_path)
            )

            # Verify download
            if not self.input_path.exists():
                print("[ERROR] Download failed - file not found")
                return False

            file_size_mb = self.input_path.stat().st_size / (1024 * 1024)
            print(f"[OK] Downloaded {file_size_mb:.2f} MB")

            return True

        except ClientError as e:
            print(f"[ERROR] S3 download failed: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] Unexpected error during download: {e}")
            return False

    def run_ffmpeg(self) -> bool:
        """
        Execute FFmpeg transcoding.

        Returns:
            True if successful, False otherwise
        """
        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build FFmpeg command
        ffmpeg_args = [
            "ffmpeg",
            "-i", str(self.input_path),
            "-y",  # Overwrite output
        ]

        # Add preset arguments
        ffmpeg_args.extend(self.preset.to_ffmpeg_args())

        # Output file
        ffmpeg_args.append(str(self.output_path))

        print("[START] Starting FFmpeg transcoding...")
        print(f"   Command: {' '.join(ffmpeg_args)}")

        start_time = time.time()

        try:
            result = subprocess.run(
                ffmpeg_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
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
            elapsed = time.time() - start_time
            print(f"[ERROR] Unexpected error after {elapsed:.1f} seconds: {e}")
            return False

    def upload_output(self) -> bool:
        """
        Upload output file to MinIO.

        Returns:
            True if successful, False otherwise
        """
        print("[START] Uploading output to MinIO...")

        try:
            # Verify output file exists
            if not self.output_path.exists():
                print(f"[ERROR] Output file not found: {self.output_path}")
                return False

            file_size_mb = self.output_path.stat().st_size / (1024 * 1024)

            if file_size_mb == 0:
                print("[ERROR] Output file is empty")
                return False

            # Upload file
            self.s3_client.upload_file(
                str(self.output_path),
                self.output_bucket,
                self.output_key
            )

            print(f"[OK] Uploaded {file_size_mb:.2f} MB to s3://{self.output_bucket}/{self.output_key}")

            return True

        except ClientError as e:
            print(f"[ERROR] S3 upload failed: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] Unexpected error during upload: {e}")
            return False

    def cleanup(self):
        """Delete temporary local files."""
        print("[CLEANUP] Removing temporary files...")

        try:
            if self.input_path.exists():
                self.input_path.unlink()
                print(f"   Deleted: {self.input_path}")
        except Exception as e:
            print(f"   Failed to delete input: {e}")

        try:
            if self.output_path.exists():
                self.output_path.unlink()
                print(f"   Deleted: {self.output_path}")
        except Exception as e:
            print(f"   Failed to delete output: {e}")

    def run(self) -> int:
        """
        Run complete transcoding workflow.

        Returns:
            Exit code (0 = success, 1 = failure)
        """
        print(f"\n{'='*60}")
        print(f"TRANSCODING JOB: {self.job_id}")
        print(f"{'='*60}\n")

        try:
            # Step 1: Download input from MinIO
            if not self.download_input():
                return 1

            # Step 2: Transcode with FFmpeg
            if not self.run_ffmpeg():
                self.cleanup()
                return 1

            # Step 3: Upload output to MinIO
            if not self.upload_output():
                self.cleanup()
                return 1

            # Step 4: Cleanup
            self.cleanup()

            print(f"\n{'='*60}")
            print(f"JOB COMPLETED SUCCESSFULLY: {self.job_id}")
            print(f"{'='*60}\n")

            return 0

        except Exception as e:
            print(f"[ERROR] Unexpected error in workflow: {e}")
            self.cleanup()
            return 1


def main():
    """
    Main entry point for transcoding worker.

    Reads configuration from environment variables and runs transcoding.
    """
    # Read S3 configuration
    s3_endpoint = os.getenv("S3_ENDPOINT")
    s3_access_key = os.getenv("S3_ACCESS_KEY")
    s3_secret_key = os.getenv("S3_SECRET_KEY")

    # Read job parameters
    input_bucket = os.getenv("INPUT_BUCKET")
    output_bucket = os.getenv("OUTPUT_BUCKET")
    input_key = os.getenv("INPUT_KEY")
    output_key = os.getenv("OUTPUT_KEY")
    preset = os.getenv("PRESET")
    job_id = os.getenv("JOB_ID")

    # Validate required env vars
    required_vars = {
        "S3_ENDPOINT": s3_endpoint,
        "S3_ACCESS_KEY": s3_access_key,
        "S3_SECRET_KEY": s3_secret_key,
        "INPUT_BUCKET": input_bucket,
        "OUTPUT_BUCKET": output_bucket,
        "INPUT_KEY": input_key,
        "OUTPUT_KEY": output_key,
        "PRESET": preset,
        "JOB_ID": job_id,
    }

    missing = [k for k, v in required_vars.items() if not v]

    if missing:
        print("[ERROR] Missing required environment variables:")
        for var in missing:
            print(f"   {var}: MISSING")
        print(f"\nAvailable presets: {', '.join(get_available_presets())}")
        sys.exit(1)

    # Create worker and run
    worker = TranscodingWorker(
        s3_endpoint=s3_endpoint,
        s3_access_key=s3_access_key,
        s3_secret_key=s3_secret_key,
        input_bucket=input_bucket,
        output_bucket=output_bucket,
        input_key=input_key,
        output_key=output_key,
        preset_name=preset,
        job_id=job_id
    )

    exit_code = worker.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()