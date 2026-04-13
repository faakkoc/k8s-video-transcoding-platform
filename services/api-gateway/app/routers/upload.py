"""
Upload router - handles video file uploads and job creation.

Updated: 09.04.2026 - MinIO S3 integration
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.models.job import JobResponse
from app.utils.validators import validate_video_file
from app.utils.k8s_client import create_transcoding_job
from app.utils.s3_client import get_s3_client
import logging
import time
from datetime import datetime
from io import BytesIO

router = APIRouter()
logger = logging.getLogger(__name__)

# Supported presets
SUPPORTED_PRESETS = ["480p", "720p", "1080p", "4k"]


@router.post("/upload", response_model=JobResponse, status_code=201)
async def upload_video(
        file: UploadFile = File(...),
        preset: str = Form(...)
):
    """
    Upload video file and create transcoding job.

    Flow:
    1. Validate file (type, size)
    2. Upload to MinIO (uploads bucket)
    3. Create Kubernetes Job with S3 paths
    4. Return job_id

    Args:
        file: Video file to upload
        preset: Transcoding preset (480p, 720p, 1080p, 4k)

    Returns:
        JobResponse with job_id and status
    """
    logger.info(f"[START] Upload request - File: {file.filename}, Preset: {preset}")

    # 1. Validate preset
    if preset not in SUPPORTED_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid preset. Supported: {', '.join(SUPPORTED_PRESETS)}"
        )

    # 2. Validate file
    try:
        validate_video_file(file)
    except ValueError as e:
        logger.error(f"[ERROR] Validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    # 3. Generate unique filename
    timestamp = int(time.time())
    original_filename = file.filename
    input_key = f"{timestamp}_{original_filename}"
    output_key = f"{timestamp}_{original_filename.rsplit('.', 1)[0]}_{preset}.mp4"

    logger.info(f"[INFO] S3 Keys - Input: {input_key}, Output: {output_key}")

    # 4. Upload to MinIO
    try:
        s3_client = get_s3_client()

        # Read file content into memory
        file_content = await file.read()
        file_obj = BytesIO(file_content)

        # Upload to uploads bucket
        success = s3_client.upload_file(
            file_obj=file_obj,
            bucket="uploads",
            key=input_key
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to upload file to storage"
            )

        logger.info(f"[OK] File uploaded to s3://uploads/{input_key}")

    except Exception as e:
        logger.error(f"[ERROR] Upload to S3 failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Storage upload failed: {str(e)}"
        )

    # 5. Create Kubernetes Job
    try:
        job_id = create_transcoding_job(
            input_key=input_key,
            output_key=output_key,
            preset=preset
        )

        logger.info(f"[OK] Job created: {job_id}")

        return JobResponse(
            job_id=job_id,
            status="pending",
            input_filename=original_filename,
            preset=preset,
            created_at=datetime.utcnow(),
            message="Job created successfully. File uploaded to storage."
        )

    except Exception as e:
        logger.error(f"[ERROR] Job creation failed: {e}")

        # Cleanup: Delete uploaded file if job creation fails
        try:
            s3_client.delete_file(bucket="uploads", key=input_key)
            logger.info(f"[CLEANUP] Deleted s3://uploads/{input_key}")
        except:
            pass

        raise HTTPException(
            status_code=500,
            detail=f"Job creation failed: {str(e)}"
        )