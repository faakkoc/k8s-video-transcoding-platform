#!/usr/bin/env python3
"""
Transcoding Worker for Kubernetes Jobs

This worker processes video transcoding jobs created by the API Gateway.
It runs as a Kubernetes Job and exits after completing the transcoding.

Environment Variables:
    INPUT_FILE: Input video filename (in /tmp/uploads)
    OUTPUT_FILE: Output video filename (for /tmp/outputs)
    PRESET: Transcoding quality preset (480p, 720p, 1080p, 4k)
    JOB_ID: Kubernetes Job ID

Date: 17.03.2026
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from typing import Optional

from ffmpeg_presets import get_preset, get_available_presets


class TranscodingWorker:
    """
    Video transcoding worker using FFmpeg.

    Handles the complete transcoding workflow:
    1. Validate inputs
    2. Run FFmpeg
    3. Verify output
    4. Report status
    """

    def __init__(
            self,
            input_file: str,
            output_file: str,
            preset_name: str,
            job_id: str
    ):
        """
        Initialize transcoding worker.

        Args:
            input_file: Input filename (without path)
            output_file: Output filename (without path)
            preset_name: Transcoding preset (480p, 720p, etc.)
            job_id: Job identifier
        """
        self.job_id = job_id
        self.preset_name = preset_name

        # File paths
        self.input_path = Path("/tmp/uploads") / input_file
        self.output_path = Path("/tmp/outputs") / output_file

        # Preset configuration
        try:
            self.preset = get_preset(preset_name)
        except ValueError as e:
            print(f"[ERROR] Invalid preset: {e}")
            sys.exit(1)

        print(f"[INIT] Transcoding Worker")
        print(f"   Job ID: {self.job_id}")
        print(f"   Preset: {self.preset_name}")
        print(f"   Input: {self.input_path}")
        print(f"   Output: {self.output_path}")

    def validate_input(self) -> bool:
        """
        Validate input file exists and is readable.

        Returns:
            True if valid, False otherwise
        """
        if not self.input_path.exists():
            print(f"[ERROR] Input file not found: {self.input_path}")
            return False

        if not self.input_path.is_file():
            print(f"[ERROR] Input is not a file: {self.input_path}")
            return False

        file_size = self.input_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)

        print(f"[OK] Input file found: {file_size_mb:.2f} MB")
        return True

    def run_ffmpeg(self) -> bool:
        """
        Execute FFmpeg transcoding.

        Returns:
            True if successful, False otherwise
        """
        # Build FFmpeg command
        ffmpeg_args = [
            "ffmpeg",
            "-i", str(self.input_path),  # Input file
            "-y",                         # Overwrite output
        ]

        # Add preset arguments
        ffmpeg_args.extend(self.preset.to_ffmpeg_args())

        # Output file
        ffmpeg_args.append(str(self.output_path))

        print(f"[START] Starting FFmpeg transcoding...")
        print(f"   Command: {' '.join(ffmpeg_args)}")

        start_time = time.time()

        try:
            # Run FFmpeg
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
            print(f"   Stderr: {e.stderr[-500:]}")  # Last 500 chars
            return False

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[ERROR] Unexpected error after {elapsed:.1f} seconds: {e}")
            return False

    def validate_output(self) -> bool:
        """
        Validate output file was created successfully.

        Returns:
            True if valid, False otherwise
        """
        if not self.output_path.exists():
            print(f"[ERROR] Output file not created: {self.output_path}")
            return False

        file_size = self.output_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)

        if file_size == 0:
            print(f"[ERROR] Output file is empty")
            return False

        print(f"[OK] Output file created: {file_size_mb:.2f} MB")
        return True

    def run(self) -> int:
        """
        Run complete transcoding workflow.

        Returns:
            Exit code (0 = success, 1 = failure)
        """
        print(f"\n{'='*60}")
        print(f"TRANSCODING JOB: {self.job_id}")
        print(f"{'='*60}\n")

        # Step 1: Validate input
        if not self.validate_input():
            return 1

        # Step 2: Run FFmpeg
        if not self.run_ffmpeg():
            return 1

        # Step 3: Validate output
        if not self.validate_output():
            return 1

        print(f"\n{'='*60}")
        print(f"JOB COMPLETED SUCCESSFULLY: {self.job_id}")
        print(f"{'='*60}\n")

        return 0


def main():
    """
    Main entry point for transcoding worker.

    Reads configuration from environment variables and runs transcoding.
    """
    # Read environment variables
    input_file = os.getenv("INPUT_FILE")
    output_file = os.getenv("OUTPUT_FILE")
    preset = os.getenv("PRESET")
    job_id = os.getenv("JOB_ID")

    # Validate required env vars
    if not all([input_file, output_file, preset, job_id]):
        print("[ERROR] Missing required environment variables:")
        print(f"   INPUT_FILE: {input_file or 'MISSING'}")
        print(f"   OUTPUT_FILE: {output_file or 'MISSING'}")
        print(f"   PRESET: {preset or 'MISSING'}")
        print(f"   JOB_ID: {job_id or 'MISSING'}")
        print(f"\nAvailable presets: {', '.join(get_available_presets())}")
        sys.exit(1)

    # Create worker and run
    worker = TranscodingWorker(
        input_file=input_file,
        output_file=output_file,
        preset_name=preset,
        job_id=job_id
    )

    exit_code = worker.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()