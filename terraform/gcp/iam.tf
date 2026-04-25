# -------------------------------------------------------------------
# GCP Service Accounts
# -------------------------------------------------------------------

resource "google_service_account" "api_gateway" {
  account_id   = "api-gateway"
  display_name = "API Gateway Service Account"
  description  = "Used by the API Gateway pod via Workload Identity"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_service_account" "transcoding_worker" {
  account_id   = "transcoding-worker"
  display_name = "Transcoding Worker Service Account"
  description  = "Used by the Transcoding Worker pods via Workload Identity"

  lifecycle {
    prevent_destroy = true
  }
}

# -------------------------------------------------------------------
# Bucket IAM
# -------------------------------------------------------------------

resource "google_storage_bucket_iam_member" "api_gateway_uploads" {
  bucket = google_storage_bucket.uploads.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.api_gateway.email}"
}

resource "google_storage_bucket_iam_member" "api_gateway_outputs" {
  bucket = google_storage_bucket.outputs.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.api_gateway.email}"
}

resource "google_storage_bucket_iam_member" "worker_uploads" {
  bucket = google_storage_bucket.uploads.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.transcoding_worker.email}"
}

resource "google_storage_bucket_iam_member" "worker_outputs" {
  bucket = google_storage_bucket.outputs.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.transcoding_worker.email}"
}

# -------------------------------------------------------------------
# Workload Identity
# -------------------------------------------------------------------

resource "google_service_account_iam_member" "api_gateway_workload_identity" {
  service_account_id = google_service_account.api_gateway.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.namespace}/api-gateway]"

  depends_on = [module.gke]
}

resource "google_service_account_iam_member" "worker_workload_identity" {
  service_account_id = google_service_account.transcoding_worker.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.namespace}/transcoding-worker]"

  depends_on = [module.gke]
}
