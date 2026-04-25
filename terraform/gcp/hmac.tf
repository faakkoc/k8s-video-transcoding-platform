resource "google_storage_hmac_key" "api_gateway" {
  service_account_email = google_service_account.api_gateway.email

  depends_on = [google_project_service.apis]

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_storage_hmac_key" "transcoding_worker" {
  service_account_email = google_service_account.transcoding_worker.email

  depends_on = [google_project_service.apis]

  lifecycle {
    prevent_destroy = true
  }
}
