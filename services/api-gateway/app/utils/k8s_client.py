"""
Kubernetes Client Wrapper for Job Management.

This module provides utilities to interact with the Kubernetes API
for creating and managing transcoding jobs.

Date: 05.03.2026
"""

import os
from typing import Dict, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException


class KubernetesJobClient:
    """
    Wrapper for Kubernetes API to manage transcoding jobs.

    Handles:
    - Job creation
    - Job status checking
    - Job cleanup
    """

    def __init__(
            self,
            namespace: str = "video-transcoding",
            in_cluster: bool = True
    ):
        """
        Initialize Kubernetes client.

        Args:
            namespace: Kubernetes namespace for jobs
            in_cluster: Whether running inside K8s cluster
        """
        self.namespace = namespace

        # Load Kubernetes config
        if in_cluster:
            # Running inside cluster - use ServiceAccount token
            config.load_incluster_config()
        else:
            # Running locally - use kubeconfig file
            config.load_kube_config()

        # Initialize API clients
        self.batch_v1 = client.BatchV1Api()
        self.core_v1 = client.CoreV1Api()


    def create_transcoding_job(
            self,
            job_id: str,
            input_filename: str,
            output_filename: str,
            preset: str,
            worker_image: str = "transcoding-worker:latest"
    ) -> Dict[str, any]:
        """
        Create a Kubernetes Job for video transcoding.

        Args:
            job_id: Unique job identifier
            input_filename: Input video filename in /tmp/uploads
            output_filename: Output video filename for /tmp/outputs
            preset: Transcoding preset (480p, 720p, 1080p, 4k)
            worker_image: Docker image for transcoding worker

        Returns:
            Dict with job information

        Raises:
            ApiException: If job creation fails
        """
        # Job name must be DNS-compliant (lowercase, no underscores)
        job_name = job_id.lower().replace("_", "-")

        # Create Job specification
        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_name,
                namespace=self.namespace,
                labels={
                    "app": "transcoding-worker",
                    "job-id": job_id,
                    "preset": preset,
                }
            ),
            spec=client.V1JobSpec(
                # Job should run once and complete
                completions=1,
                parallelism=1,

                # Retry on failure (max 3 attempts)
                backoff_limit=3,

                # Clean up after 24 hours (86400 seconds)
                ttl_seconds_after_finished=86400,

                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(
                        labels={
                            "app": "transcoding-worker",
                            "job-id": job_id,
                        }
                    ),
                    spec=client.V1PodSpec(
                        # Pod should not restart on completion
                        restart_policy="Never",

                        containers=[
                            client.V1Container(
                                name="transcoder",
                                image=worker_image,
                                image_pull_policy="IfNotPresent",

                                # Command to run transcoding
                                command=["python", "worker.py"],

                                # Environment variables for worker
                                env=[
                                    client.V1EnvVar(
                                        name="INPUT_FILE",
                                        value=input_filename
                                    ),
                                    client.V1EnvVar(
                                        name="OUTPUT_FILE",
                                        value=output_filename
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

                                # Resource limits for transcoding
                                resources=client.V1ResourceRequirements(
                                    requests={
                                        "memory": "512Mi",
                                        "cpu": "500m",
                                    },
                                    limits={
                                        "memory": "2Gi",
                                        "cpu": "2000m",
                                    }
                                ),

                                # Volume mounts for input/output
                                volume_mounts=[
                                    client.V1VolumeMount(
                                        name="uploads",
                                        mount_path="/tmp/uploads"
                                    ),
                                    client.V1VolumeMount(
                                        name="outputs",
                                        mount_path="/tmp/outputs"
                                    ),
                                ],
                            )
                        ],

                        # Volumes (emptyDir for now)
                        # TODO: Replace with shared storage (MinIO/PV)
                        volumes=[
                            client.V1Volume(
                                name="uploads",
                                empty_dir=client.V1EmptyDirVolumeSource(
                                    size_limit="10Gi"
                                )
                            ),
                            client.V1Volume(
                                name="outputs",
                                empty_dir=client.V1EmptyDirVolumeSource(
                                    size_limit="10Gi"
                                )
                            ),
                        ],
                    )
                )
            )
        )

        try:
            # Create the job
            api_response = self.batch_v1.create_namespaced_job(
                namespace=self.namespace,
                body=job
            )

            print(f"[OK] Kubernetes Job created: {job_name}")

            return {
                "job_name": job_name,
                "namespace": self.namespace,
                "status": "created",
                "uid": api_response.metadata.uid,
            }

        except ApiException as e:
            print(f"[ERROR] Failed to create job: {e}")
            raise


    def get_job_status(self, job_id: str) -> Optional[Dict[str, any]]:
        """
        Get status of a transcoding job.

        Args:
            job_id: Job identifier

        Returns:
            Dict with job status or None if not found
        """
        job_name = job_id.lower().replace("_", "-")

        try:
            # Get job information
            job = self.batch_v1.read_namespaced_job(
                name=job_name,
                namespace=self.namespace
            )

            # Extract status information
            status = {
                "job_name": job_name,
                "active": job.status.active or 0,
                "succeeded": job.status.succeeded or 0,
                "failed": job.status.failed or 0,
                "start_time": job.status.start_time,
                "completion_time": job.status.completion_time,
            }

            # Determine overall status
            if status["succeeded"] > 0:
                status["state"] = "completed"
            elif status["failed"] > 0:
                status["state"] = "failed"
            elif status["active"] > 0:
                status["state"] = "running"
            else:
                status["state"] = "pending"

            return status

        except ApiException as e:
            if e.status == 404:
                return None
            print(f"[ERROR] Failed to get job status: {e}")
            raise


    def delete_job(self, job_id: str) -> bool:
        """
        Delete a transcoding job.

        Args:
            job_id: Job identifier

        Returns:
            True if deleted, False if not found
        """
        job_name = job_id.lower().replace("_", "-")

        try:
            # Delete the job
            self.batch_v1.delete_namespaced_job(
                name=job_name,
                namespace=self.namespace,
                propagation_policy="Background"  # Also delete pods
            )

            print(f"[DELETE] Job deleted: {job_name}")
            return True

        except ApiException as e:
            if e.status == 404:
                return False
            print(f"[ERROR] Failed to delete job: {e}")
            raise


    def list_jobs(self, limit: int = 100) -> list:
        """
        List all transcoding jobs.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of job information dicts
        """
        try:
            # List jobs with label selector
            jobs = self.batch_v1.list_namespaced_job(
                namespace=self.namespace,
                label_selector="app=transcoding-worker",
                limit=limit
            )

            result = []
            for job in jobs.items:
                result.append({
                    "job_name": job.metadata.name,
                    "job_id": job.metadata.labels.get("job-id"),
                    "preset": job.metadata.labels.get("preset"),
                    "active": job.status.active or 0,
                    "succeeded": job.status.succeeded or 0,
                    "failed": job.status.failed or 0,
                    "start_time": job.status.start_time,
                    "completion_time": job.status.completion_time,
                })

            return result

        except ApiException as e:
            print(f"[ERROR] Failed to list jobs: {e}")
            raise


# Singleton instance
_k8s_client: Optional[KubernetesJobClient] = None


def get_k8s_client(
        namespace: str = None,
        in_cluster: bool = None
) -> KubernetesJobClient:
    """
    Get singleton Kubernetes client instance.

    Args:
        namespace: Override namespace (optional)
        in_cluster: Override in_cluster setting (optional)

    Returns:
        KubernetesJobClient instance
    """
    global _k8s_client

    if _k8s_client is None:
        # Get from environment if not specified
        if namespace is None:
            namespace = os.getenv("KUBERNETES_NAMESPACE", "video-transcoding")
        if in_cluster is None:
            in_cluster = os.getenv("IN_CLUSTER", "true").lower() == "true"

        _k8s_client = KubernetesJobClient(
            namespace=namespace,
            in_cluster=in_cluster
        )

    return _k8s_client