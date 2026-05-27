# GKE Terraform Infrastruktur

**Datum:** 21.04.2026
**Aktualisiert:** 27.05.2026 — us-east1, HMAC Keys entfernt, Workload Identity
**Status:** ✅ `terraform apply` erfolgreich

---

## Übersicht

Die gesamte GCP-Infrastruktur wird über Terraform provisioniert. Der Ansatz folgt dem Prinzip Infrastructure as Code: keine manuelle Konfiguration über die GCP Console, alles ist versioniert und reproduzierbar.

**Terraform Version:** v1.14.8
**GCP Provider:** `~> 6.0`
**Remote State:** `gs://k8s-transcoding-tfstate`
**Region:** `us-east1` (Iowa)

---

## Dateistruktur

```
terraform/gcp/
├── versions.tf          # Provider-Anforderungen, Remote Backend
├── providers.tf         # GCP Provider Konfiguration
├── variables.tf         # Variablen-Definitionen
├── terraform.auto.tfvars # Konkrete Werte (im Repo, keine Secrets)
├── apis.tf              # GCP APIs aktivieren
├── gke.tf               # GKE Autopilot Cluster
├── storage.tf           # GCS Buckets
├── artifact-registry.tf # Docker Registry
├── iam.tf               # Service Accounts + Workload Identity Bindings
├── github-wif.tf        # Workload Identity Federation für CI/CD
└── outputs.tf           # Outputs (Cluster-Name, Bucket-Namen, etc.)
```

> **Hinweis:** `hmac.tf` existiert nicht mehr — HMAC Keys wurden durch Workload Identity ersetzt.

**Bewusste Design-Entscheidung — Flat Structure:** Statt eines Modul-Ansatzes wurde eine flache Dateistruktur gewählt. Für ein Projekt dieser Größe ist das übersichtlicher als verschachtelte Module.

---

## Remote State Backend

```hcl
terraform {
  backend "gcs" {
    bucket = "k8s-transcoding-tfstate"
    prefix = "terraform/state"
  }
}
```

Der State-Bucket muss einmalig manuell erstellt werden:

```fish
gcloud storage buckets create gs://k8s-transcoding-tfstate \
  --project k8s-transcoding-plattform \
  --location us-east1
```

---

## GCP APIs (`apis.tf`)

```hcl
resource "google_project_service" "apis" {
  for_each = toset([
    "container.googleapis.com",
    "artifactregistry.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
  ])
  disable_on_destroy = false
}
```

`serviceusage.googleapis.com` ist explizit dabei — ohne diese API kann Terraform die anderen APIs nicht verwalten (Hühner-Ei-Problem das in der CI/CD-Phase aufgedeckt wurde).

---

## GKE Autopilot (`gke.tf`)

```hcl
module "gke" {
  source  = "terraform-google-modules/kubernetes-engine/google//modules/beta-autopilot-public-cluster"
  version = "~> 36.0"

  project_id = var.project_id
  name       = var.cluster_name
  region     = var.region  # us-east1

  release_channel     = "REGULAR"
  deletion_protection = false
  grant_registry_access = true

  depends_on = [google_project_service.apis]
}
```

**Warum `us-east1` statt `us-central1`?**

Das verwendete GKE Terraform Modul nutzt intern `random_shuffle` um Zonen auszuwählen. In `us-central1` fügt GCP regelmäßig neue Zonen hinzu — wenn Terraform dann einen Update-Lauf macht, erkennt es eine Zonen-Änderung und versucht den Cluster zu modifizieren, was GKE nicht erlaubt:

```
Error: Cluster location change not allowed.
Current locations [us-central1-a us-central1-b us-central1-c],
new locations [us-central1-a us-central1-b us-central1-c us-central1-f].
```

`us-east1` hat ein stabileres Zonen-Set (`b`, `c`, `d`) — dieses Problem tritt dort nicht auf.

**Warum Autopilot?**

- Keine Node-Pool-Konfiguration nötig
- Automatischer Scale-Up/Down
- Nodes werden nur für die Dauer der Last berechnet
- Trade-off: 60–90s Cold-Start wenn kein Node verfügbar (dokumentiert in gke-challenges.md)

---

## GCS Buckets (`storage.tf`)

```hcl
resource "google_storage_bucket" "uploads" {
  name     = "k8s-transcoding-uploads"
  location = var.region  # us-east1

  lifecycle_rule {
    condition { age = 7 }
    action    { type = "Delete" }
  }
}
```

7-Tage Lifecycle: Videos werden automatisch gelöscht — spart Kosten für ein PoC-Projekt.

---

## Artifact Registry (`artifact-registry.tf`)

```hcl
resource "google_artifact_registry_repository" "transcoding" {
  location      = var.region  # us-east1
  repository_id = "transcoding"
  format        = "DOCKER"

  lifecycle {
    prevent_destroy = true  # Überlebt terraform destroy
  }
}
```

Image-Pfad: `us-east1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/<image>:latest`

---

## Service Accounts & Workload Identity (`iam.tf`)

Zwei dedizierte GCP Service Accounts nach dem Least-Privilege-Prinzip:

```hcl
resource "google_service_account" "api_gateway" {
  account_id = "api-gateway"
}

resource "google_service_account" "transcoding_worker" {
  account_id = "transcoding-worker"
}
```

**Bucket-Berechtigungen:**

| Service Account | Bucket | Rolle |
|-----------------|--------|-------|
| api-gateway | uploads | `roles/storage.objectAdmin` |
| api-gateway | outputs | `roles/storage.objectViewer` |
| transcoding-worker | uploads | `roles/storage.objectViewer` |
| transcoding-worker | outputs | `roles/storage.objectAdmin` |

**Workload Identity Bindings:**

```hcl
resource "google_service_account_iam_member" "api_gateway_workload_identity" {
  service_account_id = google_service_account.api_gateway.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.namespace}/api-gateway]"
  depends_on         = [module.gke]
}
```

Diese Bindings verbinden den Kubernetes ServiceAccount `api-gateway` im Namespace `video-transcoding` mit dem GCP ServiceAccount `api-gateway@...`. GKE injiziert dann automatisch ein kurzlebiges Token in den Pod — kein Secret im Cluster notwendig.

> **Architektur-Entscheidung:** Der initiale Ansatz nutzte HMAC Keys um boto3 mit der S3-kompatiblen GCS-API zu verwenden. Die daraus resultierenden Probleme (Secret-Management, Reihenfolge-Abhängigkeiten, Debugging-Aufwand) führten zur Entscheidung, auf Workload Identity + native `google-cloud-storage` Library umzusteigen. Details in [gke-challenges.md](../06-lessons-learned/gke-challenges.md).

---

## WIF für GitHub Actions (`github-wif.tf`)

```hcl
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-actions-pool-v2"
  lifecycle { prevent_destroy = true }
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_provider_id = "github-actions-provider-v2"
  attribute_condition = "assertion.repository == 'faakkoc/k8s-video-transcoding-platform'"
  lifecycle { prevent_destroy = true }
}
```

GitHub Actions authentifiziert sich über OIDC ohne Service Account Keys. Details in [cicd-pipelines.md](./cicd-pipelines.md).

---

## Outputs (`outputs.tf`)

```
cluster_name                  = "video-transcoding"
cluster_location              = "us-east1"
artifact_registry_url         = "us-east1-docker.pkg.dev/k8s-transcoding-plattform/transcoding"
uploads_bucket                = "k8s-transcoding-uploads"
outputs_bucket                = "k8s-transcoding-outputs"
github_actions_service_account = "github-actions-cicd@k8s-transcoding-plattform.iam.gserviceaccount.com"
workload_identity_provider    = "projects/.../workloadIdentityPools/github-actions-pool-v2/providers/..."
kubectl_config_command        = "gcloud container clusters get-credentials video-transcoding --region us-east1 ..."
```

---

**Nächstes Dokument:** [Kubernetes Manifests](./gke-kubernetes-manifests.md)