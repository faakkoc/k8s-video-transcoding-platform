"""
Upload router for video transcoding platform.

Handles:
- Video file uploads
- File validation
- Temporary storage
- Kubernetes Job creation
"""

import os
import uuid
import aiofiles
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from datetime import datetime

from app.config import Settings, get_settings
from app.models.job import (
    TranscodingPreset,
    JobStatus,
    JobResponse,
)
from app.utils.validators import (
    validate_video_file,
    validate_file_size,
    generate_unique_filename,
)


router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
        file: UploadFile = File(..., description="Video file to upload"),
        preset: TranscodingPreset = Form(
            default=TranscodingPreset.HD_720P,
            description="Target transcoding quality"
        ),
        settings: Settings = Depends(get_settings),
):
    """
    Upload video for transcoding.

    **Workflow:**
    1. Validate file format and size
    2. Save to temporary storage
    3. Create Kubernetes Job for transcoding
    4. Return job ID for status tracking

    **Supported Formats:**
    - MP4 (.mp4)
    - QuickTime (.mov)
    - AVI (.avi)
    - Matroska (.mkv)
    - WebM (.webm)

    **Max File Size:** 500 MB

    **Returns:**
    - job_id: Unique identifier for tracking
    - status: Initial status (pending)
    - created_at: Timestamp
    """

    # Step 1: Validate file format
    original_filename, extension = validate_video_file(
        file,
        max_size_mb=settings.max_upload_size_mb
    )

    # Step 2: Generate unique filename
    unique_filename = generate_unique_filename(original_filename)
    upload_path = os.path.join(settings.upload_dir, unique_filename)

    # Step 3: Save file to temporary storage
    try:
        # Read and write file in chunks (memory-efficient for large files)
        async with aiofiles.open(upload_path, 'wb') as out_file:
            chunk_size = 1024 * 1024  # 1MB chunks
            while content := await file.read(chunk_size):
                await out_file.write(content)

    except Exception as e:
        # Clean up on error
        if os.path.exists(upload_path):
            os.remove(upload_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )

    # Step 4: Validate file size after upload
    try:
        validate_file_size(upload_path, max_size_mb=settings.max_upload_size_mb)
    except HTTPException:
        # File too large, already deleted by validator
        raise

    # Step 5: Generate unique job ID
    job_id = f"transcode-{uuid.uuid4().hex[:12]}"

    # Step 6: Create Kubernetes Job (TODO: Implement in next step)
    # For now, we just return the response without actually creating the job
    # This will be implemented when we have the transcoding worker

    print(f"📹 Video uploaded: {unique_filename}")
    print(f"🆔 Job ID: {job_id}")
    print(f"🎯 Preset: {preset.value}")
    print(f"📏 File size: {os.path.getsize(upload_path) / (1024*1024):.2f} MB")

    # Step 7: Return job information
    return JobResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        input_filename=original_filename,
        preset=preset,
        created_at=datetime.utcnow(),
    )


@router.get("/test")
async def test_upload_endpoint():
    """
    Test endpoint to verify upload router is working.

    Returns basic information about the upload configuration.
    """
    settings = get_settings()

    return {
        "message": "Upload endpoint is ready",
        "upload_dir": settings.upload_dir,
        "max_upload_size_mb": settings.max_upload_size_mb,
        "allowed_formats": [".mp4", ".mov", ".avi", ".mkv", ".webm"],
    }