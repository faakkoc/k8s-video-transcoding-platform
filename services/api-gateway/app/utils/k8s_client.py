"""
Kubernetes client for creating and querying transcoding jobs.

Updated: 19.04.2026 - Added job status and metadata retrieval
"""

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
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
        config.load_incluster_config()
        logger.info("[OK] Loaded in-cluster Kubernetes config")
    except config.ConfigException:
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

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    job_id = f"transcode-{timestamp}-{preset}"

    logger.info(f"[START] Creating job: {job_id}")

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
            ttl_seconds_after_finished=86400,
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
                            image="transcoding-worker:latest",
                            image_pull_policy="IfNotPresent",
                            env=[
                                client.V1EnvVar(name="S3_ENDPOINT", value="http://minio:9000"),
                                client.V1EnvVar(name="S3_ACCESS_KEY", value="minioadmin"),
                                client.V1EnvVar(name="S3_SECRET_KEY", value="minioadmin123"),
                                client.V1EnvVar(name="INPUT_BUCKET", value="uploads"),
                                client.V1EnvVar(name="OUTPUT_BUCKET", value="outputs"),
                                client.V1EnvVar(name="INPUT_KEY", value=input_key),
                                client.V1EnvVar(name="OUTPUT_KEY", value=output_key),
                                client.V1EnvVar(name="PRESET", value=preset),
                                client.V1EnvVar(name="JOB_ID", value=job_id),
                            ],
                            resources=client.V1ResourceRequirements(
                                requests={"memory": "512Mi", "cpu": "500m"},
                                limits={"memory": "2Gi", "cpu": "2000m"}
                            ),
                        )
                    ],
                )
            )
        )
    )

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


def get_job_status(job_id: str) -> dict:
    """
    Get status and metadata of a transcoding job from Kubernetes.

    Reads job status from K8s Job object and metadata from container
    ENV vars (INPUT_KEY, OUTPUT_KEY, PRESET are stored there at creation time).

    Args:
        job_id: Kubernetes Job name (e.g., "transcode-20260413-201024-720p")

    Returns:
        dict with status, output_key, preset, input_key

    Raises:
        ApiException: If job not found (404) or other K8s error
    """
    k8s_client = get_k8s_client()
    namespace = os.getenv("K8S_NAMESPACE", "video-transcoding")

    try:
        job = k8s_client.read_namespaced_job(name=job_id, namespace=namespace)
    except ApiException as e:
        if e.status == 404:
            raise ApiException(status=404, reason=f"Job '{job_id}' not found")
        raise

    # Determine status from job.status fields
    status = _parse_job_status(job.status)

    # Read metadata from container ENV vars
    env_vars = job.spec.template.spec.containers[0].env
    env_map = {e.name: e.value for e in env_vars}

    return {
        "job_id": job_id,
        "status": status,
        "input_key": env_map.get("INPUT_KEY"),
        "output_key": env_map.get("OUTPUT_KEY"),
        "preset": env_map.get("PRESET"),
        "start_time": job.status.start_time,
        "completion_time": job.status.completion_time,
    }


def _parse_job_status(job_status) -> str:
    """
    Convert Kubernetes Job status fields to a simple status string.

    Kubernetes Job status works via counters:
    - active > 0  → job is running (or retrying)
    - succeeded > 0 → job completed successfully
    - failed > 0 and active == 0 → job failed permanently

    Args:
        job_status: kubernetes.client.V1JobStatus object

    Returns:
        One of: "pending", "running", "completed", "failed"
    """
    active = job_status.active or 0
    succeeded = job_status.succeeded or 0
    failed = job_status.failed or 0

    if succeeded > 0:
        return "completed"
    elif active > 0:
        return "running"
    elif failed > 0 and active == 0:
        return "failed"
    else:
        return "pending"