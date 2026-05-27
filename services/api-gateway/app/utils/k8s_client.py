"""
Kubernetes client for creating and querying transcoding jobs.
Updated: 26.04.2026 - Removed S3 credentials for GCS (Workload Identity)
Updated: 27.05.2026 - Restored get_job_status and _parse_job_status
"""
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
import os
import logging

logger = logging.getLogger(__name__)


def get_k8s_client():
    """Initialize Kubernetes client (in-cluster or local kubeconfig)."""
    try:
        config.load_incluster_config()
        logger.info("[K8S] Using in-cluster config")
    except config.ConfigException:
        config.load_kube_config()
        logger.info("[K8S] Using local kubeconfig")
    return client.BatchV1Api()


def create_transcoding_job(
        input_key: str,
        output_key: str,
        preset: str,
) -> str:
    """
    Create a Kubernetes Job for video transcoding.

    Args:
        input_key: Input file key in storage bucket
        output_key: Output file key in storage bucket
        preset: Transcoding preset name

    Returns:
        job_id: Name of the created Kubernetes Job
    """
    import time
    timestamp = int(time.time())
    job_id = f"transcode-{timestamp}-{preset}"
    namespace = os.getenv("K8S_NAMESPACE", "video-transcoding")
    storage_provider = os.getenv("STORAGE_PROVIDER", "s3")

    # Base env vars — always required
    env_vars = [
        client.V1EnvVar(name="STORAGE_PROVIDER", value=storage_provider),
        client.V1EnvVar(name="INPUT_BUCKET",      value=os.getenv("INPUT_BUCKET", "uploads")),
        client.V1EnvVar(name="OUTPUT_BUCKET",     value=os.getenv("OUTPUT_BUCKET", "outputs")),
        client.V1EnvVar(name="INPUT_KEY",         value=input_key),
        client.V1EnvVar(name="OUTPUT_KEY",        value=output_key),
        client.V1EnvVar(name="PRESET",            value=preset),
        client.V1EnvVar(name="JOB_ID",            value=job_id),
    ]

    # S3 credentials only needed for S3 provider (MinIO, StackIT)
    if storage_provider == "s3":
        env_vars.extend([
            client.V1EnvVar(name="S3_ENDPOINT",   value=os.getenv("S3_ENDPOINT", "http://minio:9000")),
            client.V1EnvVar(name="S3_ACCESS_KEY",  value=os.getenv("WORKER_S3_ACCESS_KEY", "minioadmin")),
            client.V1EnvVar(name="S3_SECRET_KEY",  value=os.getenv("WORKER_S3_SECRET_KEY", "minioadmin123")),
            client.V1EnvVar(name="S3_REGION",      value=os.getenv("S3_REGION", "us-east-1")),
        ])

    batch_v1 = get_k8s_client()

    job = client.V1Job(
        metadata=client.V1ObjectMeta(
            name=job_id,
            namespace=namespace,
            labels={"app": "transcoding-worker", "job-id": job_id}
        ),
        spec=client.V1JobSpec(
            backoff_limit=2,
            ttl_seconds_after_finished=3600,
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={"app": "transcoding-worker"}
                ),
                spec=client.V1PodSpec(
                    restart_policy="Never",
                    service_account_name="transcoding-worker",
                    containers=[
                        client.V1Container(
                            name="transcoder",
                            image=os.getenv("TRANSCODING_WORKER_IMAGE", "transcoding-worker:latest"),
                            image_pull_policy=os.getenv("IMAGE_PULL_POLICY", "IfNotPresent"),
                            env=env_vars,
                            resources=client.V1ResourceRequirements(
                                requests={"memory": "512Mi", "cpu": "500m"},
                                limits={"memory": "2Gi",    "cpu": "2000m"}
                            )
                        )
                    ]
                )
            )
        )
    )

    try:
        batch_v1.create_namespaced_job(namespace=namespace, body=job)
        logger.info(f"[OK] Created job: {job_id}")
        return job_id
    except ApiException as e:
        logger.error(f"[ERROR] Failed to create job: {e}")
        raise


def get_job_status(job_id: str) -> dict:
    """
    Get status and metadata of a transcoding job from Kubernetes.

    Reads job status from K8s Job object and metadata from container
    ENV vars (INPUT_KEY, OUTPUT_KEY, PRESET are stored there at creation time).

    Args:
        job_id: Kubernetes Job name (e.g., "transcode-20260421-191719-720p")

    Returns:
        dict with status, output_key, preset, input_key

    Raises:
        ApiException: If job not found (404) or other K8s error
    """
    batch_v1 = get_k8s_client()
    namespace = os.getenv("K8S_NAMESPACE", "video-transcoding")

    job = batch_v1.read_namespaced_job(name=job_id, namespace=namespace)

    job_status = _parse_job_status(job.status)

    env_vars = job.spec.template.spec.containers[0].env
    env_map = {e.name: e.value for e in env_vars}

    return {
        "job_id": job_id,
        "status": job_status,
        "input_key": env_map.get("INPUT_KEY"),
        "output_key": env_map.get("OUTPUT_KEY"),
        "preset": env_map.get("PRESET"),
        "start_time": job.status.start_time,
        "completion_time": job.status.completion_time,
    }


def _parse_job_status(job_status) -> str:
    """
    Convert Kubernetes Job status fields to a simple status string.

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