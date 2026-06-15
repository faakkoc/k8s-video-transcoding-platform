"""
Pydantic models for transcoding jobs.

These models define the structure of API requests and responses.
FastAPI uses them for:
- Automatic request validation
- API documentation (Swagger UI)
- Type safety

Note: Job status/download response models (JobStatusResponse,
DownloadResponse) are defined directly in app/routers/jobs.py, since
they're only used there. This module covers the upload response and
the shared enums used across routers.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class TranscodingPreset(str, Enum):
    """
    Available transcoding presets.

    Using Enum ensures only valid presets can be selected.
    """
    SD_480P = "480p"
    HD_720P = "720p"
    FULL_HD_1080P = "1080p"
    UHD_4K = "4k"


class JobStatus(str, Enum):
    """
    Job lifecycle status.

    Represents the current state of a transcoding job.
    """
    PENDING = "pending"      # Job created, not yet started
    RUNNING = "running"      # Transcoding in progress
    COMPLETED = "completed"  # Successfully finished
    FAILED = "failed"        # Error occurred
    CANCELLED = "cancelled"  # User cancelled


class JobResponse(BaseModel):
    """
    Response after creating a transcoding job.

    Returns essential information about the created job.
    """
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    input_filename: str = Field(..., description="Original filename")
    preset: TranscodingPreset = Field(..., description="Selected quality preset")
    created_at: datetime = Field(..., description="Job creation timestamp")
    message: Optional[str] = Field(
        default=None,
        description="Human-readable status message"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "transcode-1781044594-a1b2c3-720p",
                "status": "pending",
                "input_filename": "vacation_2026.mp4",
                "preset": "720p",
                "created_at": "2026-02-08T10:30:00Z",
                "message": "Job created successfully. File uploaded to storage."
            }
        }