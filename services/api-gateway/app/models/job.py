"""
Pydantic models for transcoding jobs.

These models define the structure of API requests and responses.
FastAPI uses them for:
- Automatic request validation
- API documentation (Swagger UI)
- Type safety
"""

from pydantic import BaseModel, Field
from typing import Optional, List
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


class UploadRequest(BaseModel):
    """
    Request model for video upload.

    Optional parameters that can be sent with upload:
    - preset: Target quality (default: 720p)
    - filename: Custom output filename
    """
    preset: TranscodingPreset = Field(
        default=TranscodingPreset.HD_720P,
        description="Target transcoding quality"
    )
    output_filename: Optional[str] = Field(
        default=None,
        description="Custom output filename (optional)"
    )

    class Config:
        # Example for API documentation
        json_schema_extra = {
            "example": {
                "preset": "720p",
                "output_filename": "my_video_720p.mp4"
            }
        }


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

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "transcode-abc123def456",
                "status": "pending",
                "input_filename": "vacation_2026.mp4",
                "preset": "720p",
                "created_at": "2026-02-08T10:30:00Z"
            }
        }


class JobStatusResponse(BaseModel):
    """
    Detailed job status information.

    Used for GET /api/v1/jobs/{job_id} endpoint.
    """
    job_id: str
    status: JobStatus
    input_filename: str
    output_filename: Optional[str]
    preset: TranscodingPreset
    progress: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Processing progress in percent"
    )
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "transcode-abc123def456",
                "status": "running",
                "input_filename": "vacation_2026.mp4",
                "output_filename": "vacation_2026_720p.mp4",
                "preset": "720p",
                "progress": 45,
                "created_at": "2026-02-08T10:30:00Z",
                "started_at": "2026-02-08T10:30:15Z",
                "completed_at": None,
                "error_message": None
            }
        }


class JobListResponse(BaseModel):
    """
    List of jobs.

    Used for GET /api/v1/jobs endpoint.
    """
    jobs: List[JobStatusResponse]
    total: int = Field(..., description="Total number of jobs")

    class Config:
        json_schema_extra = {
            "example": {
                "jobs": [
                    {
                        "job_id": "transcode-abc123",
                        "status": "completed",
                        "input_filename": "video1.mp4",
                        "preset": "720p",
                        "created_at": "2026-02-08T10:00:00Z"
                    }
                ],
                "total": 1
            }
        }