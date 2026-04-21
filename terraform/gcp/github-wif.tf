# -------------------------------------------------------------------
# Workload Identity Federation für GitHub Actions
# -------------------------------------------------------------------

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "WIF Pool für GitHub Actions CI/CD"

  depends_on = [google_project_service.apis]

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider"
  display_name                       = "GitHub Actions Provider"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  attribute_condition = "assertion.repository == '${var.github_repository}'"

  lifecycle {
    prevent_destroy = true
  }
}

# CI/CD Service Account
resource "google_service_account" "github_actions" {
  account_id   = "github-actions-cicd"
  display_name = "GitHub Actions CI/CD Service Account"
  description  = "Wird von GitHub Actions für Terraform und Docker Push genutzt"

  lifecycle {
    prevent_destroy = true
  }
}

# WIF Binding
resource "google_service_account_iam_member" "github_actions_wif" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"

  lifecycle {
    prevent_destroy = true
  }
}

# Berechtigungen
resource "google_project_iam_member" "github_actions_artifact_registry" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_actions.email}"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "github_actions_gke" {
  project = var.project_id
  role    = "roles/container.developer"
  member  = "serviceAccount:${google_service_account.github_actions.email}"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "github_actions_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.github_actions.email}"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "github_actions_editor" {
  project = var.project_id
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.github_actions.email}"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "github_actions_iam" {
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.github_actions.email}"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "github_actions_serviceusage" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageAdmin"
  member  = "serviceAccount:${google_service_account.github_actions.email}"

  lifecycle {
    prevent_destroy = true
  }
}
