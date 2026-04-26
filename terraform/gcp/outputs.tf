output "cluster_name" {
  description = "GKE cluster name"
  value       = module.gke.name
}

output "cluster_location" {
  description = "GKE cluster location"
  value       = module.gke.location
}

output "artifact_registry_url" {
  description = "Docker image URL prefix for Artifact Registry"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_name}"
}

output "uploads_bucket" {
  description = "GCS bucket name for input videos"
  value       = google_storage_bucket.uploads.name
}

output "outputs_bucket" {
  description = "GCS bucket name for transcoded videos"
  value       = google_storage_bucket.outputs.name
}

output "api_gateway_service_account" {
  description = "GCP Service Account email for API Gateway"
  value       = google_service_account.api_gateway.email
}

output "worker_service_account" {
  description = "GCP Service Account email for Transcoding Worker"
  value       = google_service_account.transcoding_worker.email
}

output "kubectl_config_command" {
  description = "Command to configure kubectl for this cluster"
  value       = "gcloud container clusters get-credentials ${var.cluster_name} --region ${var.region} --project ${var.project_id}"
}

# GitHub Actions CI/CD
output "github_actions_service_account" {
  description = "Service Account Email für GitHub Actions"
  value       = google_service_account.github_actions.email
}

output "workload_identity_provider" {
  description = "WIF Provider Resource Name für GitHub Actions"
  value       = google_iam_workload_identity_pool_provider.github.name
}
