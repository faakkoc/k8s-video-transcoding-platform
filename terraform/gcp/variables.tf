variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for all resources"
  type        = string
}

variable "cluster_name" {
  description = "GKE cluster name"
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace"
  type        = string
}

variable "uploads_bucket_name" {
  description = "GCS bucket name for input videos"
  type        = string
}

variable "outputs_bucket_name" {
  description = "GCS bucket name for transcoded videos"
  type        = string
}

variable "artifact_registry_name" {
  description = "Artifact Registry repository name"
  type        = string
}
variable "github_repository" {
  description = "GitHub Repository im Format 'owner/repo' (z.B. 'faakkoc/k8s-video-transcoding-platform')"
  type        = string
}
