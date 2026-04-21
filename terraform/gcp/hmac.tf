# HMAC Key for API Gateway Service Account
# Allows boto3 to authenticate against GCS S3-compatible API
resource "google_storage_hmac_key" "api_gateway" {
  service_account_email = google_service_account.api_gateway.email

  depends_on = [google_project_service.apis]
}

# HMAC Key for Transcoding Worker Service Account
resource "google_storage_hmac_key" "transcoding_worker" {
  service_account_email = google_service_account.transcoding_worker.email

  depends_on = [google_project_service.apis]
}
