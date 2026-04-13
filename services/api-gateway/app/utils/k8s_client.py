"""
Kubernetes client for creating transcoding jobs.

Updated: 09.04.2026 - S3 integration
"""

from kubernetes import client, config
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_k8s_client():
    """
    Initialize Kubernetes client.

    Loads config from:
    - In-cluster config (when running in K8s)
    - Kubeconfig file (local development)
    """
    try:
        # Try in-cluster config first
        config.load_incluster_config()
        logger.info("[OK] Loaded in-cluster Kubernetes config")
    except config.ConfigException:
        # Fall back to kubeconfig
        config.load_kube_config()
        logger.info("[OK] Loaded kubeconfig from local environment")

    return client.BatchV1Api()


def create_transcoding_job(
        input_key: str,
        output_key: str,
        preset: str
) -> str:
    """
    Create Kubernetes Job for video transcoding.

    Args:
        input_key: S3 key for input file (e.g., "1234567890_video.mp4")
        output_key: S3 key for output file (e.g., "1234567890_video_720p.mp4")
        preset: Transcoding preset (480p, 720p, 1080p, 4k)

    Returns:
        job_id: Unique job identifier
    """
    k8s_client = get_k8s_client()

    # Generate unique job ID
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    job_id = f"transcode-{timestamp}-{preset}"

    logger.info(f"[START] Creating job: {job_id}")

    # Job manifest
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(
            name=job_id,
            namespace=os.getenv("K8S_NAMESPACE", "video-transcoding"),
            labels={
                "app": "transcoding-worker",
                "preset": preset,
                "job-type": "video-transcode"
            }
        ),
        spec=client.V1JobSpec(
            completions=1,
            parallelism=1,
            backoff_limit=3,
            ttl_seconds_after_finished=86400,  # 24h cleanup
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={
                        "app": "transcoding-worker",
                        "job-id": job_id
                    }
                ),
                spec=client.V1PodSpec(
                    restart_policy="Never",
                    containers=[
                        client.V1Container(
                            name="transcoder",
                            image="kind-registry:5000/transcoding-worker:v1",
                            image_pull_policy="Always",  # Kind: use local image
                            env=[
                                # S3 Configuration
                                client.V1EnvVar(
                                    name="S3_ENDPOINT",
                                    value="http://minio:9000"
                                ),
                                client.V1EnvVar(
                                    name="S3_ACCESS_KEY",
                                    value="minioadmin"
                                ),
                                client.V1EnvVar(
                                    name="S3_SECRET_KEY",
                                    value="minioadmin123"
                                ),
                                # Job Parameters
                                client.V1EnvVar(
                                    name="INPUT_BUCKET",
                                    value="uploads"
                                ),
                                client.V1EnvVar(
                                    name="OUTPUT_BUCKET",
                                    value="outputs"
                                ),
                                client.V1EnvVar(
                                    name="INPUT_KEY",
                                    value=input_key
                                ),
                                client.V1EnvVar(
                                    name="OUTPUT_KEY",
                                    value=output_key
                                ),
                                client.V1EnvVar(
                                    name="PRESET",
                                    value=preset
                                ),
                                client.V1EnvVar(
                                    name="JOB_ID",
                                    value=job_id
                                ),
                            ],
                            resources=client.V1ResourceRequirements(
                                requests={
                                    "memory": "512Mi",
                                    "cpu": "500m"
                                },
                                limits={
                                    "memory": "2Gi",
                                    "cpu": "2000m"
                                }
                            ),
                        )
                    ],
                )
            )
        )
    )

    # Create job
    try:
        k8s_client.create_namespaced_job(
            namespace=os.getenv("K8S_NAMESPACE", "video-transcoding"),
            body=job
        )
        logger.info(f"[OK] Job created: {job_id}")
        logger.info(f"     Input: s3://uploads/{input_key}")
        logger.info(f"     Output: s3://outputs/{output_key}")
        logger.info(f"     Preset: {preset}")

        return job_id

    except Exception as e:
        logger.error(f"[ERROR] Job creation failed: {e}")
        raise