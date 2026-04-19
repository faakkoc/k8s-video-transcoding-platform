"""
Jobs router - job status and download endpoints.

Added: 19.04.2026
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from kubernetes.client.exceptions import ApiException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.utils.k8s_client import get_job_status
from app.utils.s3_client import get_s3_client

router = APIRouter()


class JobStatusResponse(BaseModel):
    """Response model for job status endpoint."""
    job_id: str
    status: str
    preset: Optional[str] = None
    input_key: Optional[str] = None
    output_key: Optional[str] = None
    start_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "transcode-20260413-201024-720p",
                "status": "completed",
                "preset": "720p",
                "input_key": "1776111023_test-video.mp4",
                "output_key": "1776111023_test-video_720p.mp4",
                "start_time": "2026-04-13T20:10:24Z",
                "completion_time": "2026-04-13T20:10:30Z"
            }
        }


class DownloadResponse(BaseModel):
    """Response model for download endpoint."""
    job_id: str
    output_key: str
    download_url: str
    expires_in_seconds: int = 3600

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "transcode-20260413-201024-720p",
                "output_key": "1776111023_test-video_720p.mp4",
                "download_url": "http://minio:9000/outputs/...",
                "expires_in_seconds": 3600
            }
        }


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str):
    """
    Get status and metadata of a transcoding job.

    Reads job state from the Kubernetes Job object.
    Metadata (input_key, output_key, preset) is read from
    the container ENV vars stored at job creation time.

    Args:
        job_id: Job identifier (e.g., "transcode-20260413-201024-720p")

    Returns:
        JobStatusResponse with current status and metadata

    Raises:
        404: If job not found in Kubernetes
        500: If Kubernetes API call fails
    """
    try:
        job_data = get_job_status(job_id)
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Job '{job_id}' not found"
            )
        raise HTTPException(
            status_code=500,
            detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve job status: {str(e)}"
        )

    return JobStatusResponse(**job_data)


@router.get("/download/{job_id}", response_model=DownloadResponse)
async def download_job(job_id: str):
    """
    Generate a presigned download URL for a completed transcoding job.

    Reads the output_key from the Kubernetes Job ENV vars and
    generates a time-limited presigned URL from MinIO.

    Args:
        job_id: Job identifier (e.g., "transcode-20260413-201024-720p")

    Returns:
        DownloadResponse with presigned URL (valid 1 hour)

    Raises:
        404: If job not found
        409: If job is not yet completed
        500: If URL generation fails
    """
    # 1. Get job metadata from Kubernetes
    try:
        job_data = get_job_status(job_id)
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Job '{job_id}' not found"
            )
        raise HTTPException(
            status_code=500,
            detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve job: {str(e)}"
        )

    # 2. Check job is completed
    if job_data["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Job is not completed yet. Current status: {job_data['status']}"
        )

    # 3. Get output_key
    output_key = job_data.get("output_key")
    if not output_key:
        raise HTTPException(
            status_code=500,
            detail="Could not determine output file key from job metadata"
        )

    # 4. Generate presigned URL from MinIO
    s3_client = get_s3_client()
    expiration = 3600  # 1 hour

    download_url = s3_client.get_file_url(
        bucket="outputs",
        key=output_key,
        expiration=expiration
    )

    if not download_url:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate download URL"
        )

    return DownloadResponse(
        job_id=job_id,
        output_key=output_key,
        download_url=download_url,
        expires_in_seconds=expiration
    )