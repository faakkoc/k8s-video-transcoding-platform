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

output "api_gateway_hmac_access_key" {
  description = "HMAC Access Key ID for API Gateway (use for S3_ACCESS_KEY)"
  value       = google_storage_hmac_key.api_gateway.access_id
}

output "api_gateway_hmac_secret" {
  description = "HMAC Secret for API Gateway (use for S3_SECRET_KEY)"
  value       = google_storage_hmac_key.api_gateway.secret
  sensitive   = true
}

output "worker_hmac_access_key" {
  description = "HMAC Access Key ID for Transcoding Worker"
  value       = google_storage_hmac_key.transcoding_worker.access_id
}

output "worker_hmac_secret" {
  description = "HMAC Secret for Transcoding Worker"
  value       = google_storage_hmac_key.transcoding_worker.secret
  sensitive   = true
}
# Diese Outputs werden als GitHub Actions Secrets/Variables gesetzt
output "github_actions_service_account" {
  description = "Service Account Email für GitHub Actions"
  value       = google_service_account.github_actions.email
}

output "workload_identity_provider" {
  description = "WIF Provider Resource Name für GitHub Actions"
  value       = google_iam_workload_identity_pool_provider.github.name
}
