# -------------------------------------------------------------------
# Workload Identity Federation für GitHub Actions
#
# Ermöglicht GitHub Actions sich ohne Service Account Key bei GCP
# zu authentifizieren. GitHub Actions beweist seine Identität über
# OIDC-Token, GCP verifiziert den Token gegen den WIF Pool.
# -------------------------------------------------------------------

# WIF Pool — Sammlung von externen Identitäten
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "WIF Pool für GitHub Actions CI/CD"

  depends_on = [google_project_service.apis]
}

# WIF Provider — definiert wie GitHub Actions Tokens validiert werden
resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider"
  display_name                       = "GitHub Actions Provider"

  # GitHub OIDC Endpoint
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  # Mapping: GitHub Token Claims → GCP Attribute
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  # Nur Tokens aus diesem Repository werden akzeptiert
  attribute_condition = "assertion.repository == '${var.github_repository}'"
}

# CI/CD Service Account — führt Terraform und Docker Push aus
resource "google_service_account" "github_actions" {
  account_id   = "github-actions-cicd"
  display_name = "GitHub Actions CI/CD Service Account"
  description  = "Wird von GitHub Actions für Terraform und Docker Push genutzt"
}

# WIF Binding: GitHub Actions → CI/CD Service Account
resource "google_service_account_iam_member" "github_actions_wif" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

# Berechtigungen für den CI/CD Service Account
# Artifact Registry: Images pushen
resource "google_project_iam_member" "github_actions_artifact_registry" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

# GKE: kubectl rollout restart ausführen
resource "google_project_iam_member" "github_actions_gke" {
  project = var.project_id
  role    = "roles/container.developer"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

# Terraform State: GCS Bucket lesen/schreiben
resource "google_project_iam_member" "github_actions_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

# Terraform: GCP Ressourcen verwalten (Editor für terraform apply)
resource "google_project_iam_member" "github_actions_editor" {
  project = var.project_id
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

# IAM Admin für Workload Identity Bindings via Terraform
resource "google_project_iam_member" "github_actions_iam" {
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

