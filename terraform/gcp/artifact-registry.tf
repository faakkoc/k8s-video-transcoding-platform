resource "google_artifact_registry_repository" "transcoding" {
  location      = var.region
  repository_id = var.artifact_registry_name
  format        = "DOCKER"
  description   = "Docker images for video transcoding platform"

  depends_on = [google_project_service.apis]

  lifecycle {
    prevent_destroy = true
  }
}
