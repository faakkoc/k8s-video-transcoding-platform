resource "google_storage_bucket" "uploads" {
  name          = var.uploads_bucket_name
  location      = var.region
  force_destroy = true

  lifecycle_rule {
    condition { age = 7 }
    action { type = "Delete" }
  }

  depends_on = [google_project_service.apis]

  # lifecycle {
  #   prevent_destroy = true
  # }
}

resource "google_storage_bucket" "outputs" {
  name          = var.outputs_bucket_name
  location      = var.region
  force_destroy = true

  lifecycle_rule {
    condition { age = 7 }
    action { type = "Delete" }
  }

  depends_on = [google_project_service.apis]

  # lifecycle {
  #   prevent_destroy = true
  # }
}
