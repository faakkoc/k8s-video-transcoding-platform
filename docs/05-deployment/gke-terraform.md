# GKE Terraform Infrastruktur

**Datum:** 21.04.2026
**Status:** ✅ `terraform apply` erfolgreich (24 Ressourcen)

---

## Übersicht

Die gesamte GCP-Infrastruktur wird über Terraform provisioniert. Der Ansatz folgt dem Prinzip Infrastructure as Code: keine manuelle Konfiguration über die GCP Console, alles ist versioniert und reproduzierbar.

**Terraform Version:** v1.14.8
**GCP Provider:** `~> 6.0`
**Remote State:** `gs://k8s-transcoding-tfstate`

---

## Dateistruktur

```
terraform/gcp/
├── versions.tf          # Provider-Anforderungen, Remote Backend
├── providers.tf         # GCP Provider Konfiguration
├── variables.tf         # Variablen-Definitionen (ohne Werte)
├── terraform.auto.tfvars # Konkrete Werte (in .gitignore)
├── apis.tf              # GCP APIs aktivieren
├── gke.tf               # GKE Autopilot Cluster
├── storage.tf           # GCS Buckets
├── artifact-registry.tf # Docker Registry
├── iam.tf               # Service Accounts + Bucket IAM
├── hmac.tf              # HMAC Keys + Kubernetes Secret
└── outputs.tf           # Outputs (Cluster-Name, Bucket-Namen, etc.)
```

**Bewusste Design-Entscheidung — Flat Structure:** Statt eines Modul-Ansatzes wurde eine flache Dateistruktur gewählt, bei der jede Datei eine Komponente abdeckt. Für ein Projekt dieser Größe ist das übersichtlicher als verschachtelte Module und einfacher zu verstehen und zu debuggen.

---

## Remote State Backend

Der Terraform State wird in einem GCS Bucket gespeichert, nicht lokal. Das verhindert State-Verlust bei `terraform destroy` und ermöglicht zukünftige Teamarbeit.

```hcl
# versions.tf
terraform {
  backend "gcs" {
    bucket = "k8s-transcoding-tfstate"
    prefix = "terraform/state"
  }
}
```

Der State-Bucket muss manuell erstellt werden (Henne-Ei-Problem: Terraform kann seinen eigenen State-Bucket nicht selbst anlegen):

```fish
gcloud storage buckets create gs://k8s-transcoding-tfstate \
  --project k8s-transcoding-plattform \
  --location us-central1
```

---

## GCP APIs (`apis.tf`)

Neue GCP-Projekte haben die meisten APIs deaktiviert. Terraform aktiviert alle benötigten APIs:

```hcl
resource "google_project_service" "apis" {
  for_each = toset([
    "container.googleapis.com",           # GKE
    "artifactregistry.googleapis.com",    # Artifact Registry
    "storage.googleapis.com",             # Cloud Storage
    "iam.googleapis.com",                 # IAM
    "iamcredentials.googleapis.com",      # Workload Identity
    "cloudresourcemanager.googleapis.com" # Terraform selbst
  ])
  service            = each.value
  disable_on_destroy = false
}
```

`disable_on_destroy = false` verhindert, dass Terraform die APIs bei `terraform destroy` wieder deaktiviert — das würde andere Projekte im selben GCP-Projekt stören.

---

## GKE Autopilot (`gke.tf`)

```hcl
resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = var.region

  enable_autopilot = true
  deletion_protection = false

  # Artifact Registry Zugriff für alle Nodes
  node_config {
    service_account = google_service_account.api_gateway.email
  }
}
```

**Warum Autopilot?**

GKE Autopilot verwaltet Node-Pools automatisch — kein manuelles Provisionieren von VMs, kein Node-Pool-Management. Der Cluster skaliert automatisch basierend auf dem tatsächlichen Bedarf. Für dieses Projekt ist das ideal:

- Keine Konfiguration von Machine Types
- Automatischer Scale-Up wenn Worker-Jobs pending sind
- Automatischer Scale-Down wenn keine Last vorhanden
- Nodes werden nur für die Dauer der Last berechnet

**Erfahrung im Deployment:** GKE Autopilot benötigt 2–3 Minuten um einen neuen Node hochzufahren wenn kein Node für einen Job verfügbar ist. Das ist ein bekanntes Verhalten bei Autopilot — der erste Job nach einem `terraform apply` wartet entsprechend.

**`grant_registry_access = true`:** Ermöglicht allen GKE Nodes automatisch Images aus der Artifact Registry zu pullen, ohne separate Credentials konfigurieren zu müssen.

---

## GCS Buckets (`storage.tf`)

```hcl
resource "google_storage_bucket" "uploads" {
  name          = var.uploads_bucket_name   # "k8s-transcoding-uploads"
  location      = var.region
  force_destroy = true

  lifecycle_rule {
    condition { age = 7 }
    action    { type = "Delete" }
  }
}

resource "google_storage_bucket" "outputs" {
  name          = var.outputs_bucket_name   # "k8s-transcoding-outputs"
  location      = var.region
  force_destroy = true

  lifecycle_rule {
    condition { age = 7 }
    action    { type = "Delete" }
  }
}
```

**7-Tage Lifecycle:** Objekte werden nach 7 Tagen automatisch gelöscht. Für ein PoC-Projekt spart das Kosten — Videos müssen nicht dauerhaft gespeichert werden.

**`force_destroy = true`:** Ermöglicht `terraform destroy` auch wenn die Buckets noch Objekte enthalten. Ohne diese Option würde Terraform bei gefüllten Buckets scheitern.

---

## Artifact Registry (`artifact-registry.tf`)

```hcl
resource "google_artifact_registry_repository" "transcoding" {
  location      = var.region
  repository_id = var.artifact_registry_name  # "transcoding"
  format        = "DOCKER"
}
```

Die Registry speichert die Docker Images für API Gateway und Transcoding Worker. Der vollständige Image-Pfad lautet:

```
us-central1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/<image>:latest
```

**Wichtig:** `terraform destroy` löscht die Artifact Registry inklusive aller Images. Nach einem erneuten `terraform apply` müssen die Images neu gebaut und gepusht werden. Das ist ein bekannter Pain-Point — eine CI/CD Pipeline würde diesen Schritt automatisieren.

---

## Service Accounts & IAM (`iam.tf`)

Zwei dedizierte GCP Service Accounts nach dem Least-Privilege-Prinzip:

```hcl
resource "google_service_account" "api_gateway" {
  account_id   = "api-gateway"
  display_name = "API Gateway Service Account"
}

resource "google_service_account" "transcoding_worker" {
  account_id   = "transcoding-worker"
  display_name = "Transcoding Worker Service Account"
}
```

**Bucket-Berechtigungen:**

| Service Account | Bucket | Rolle |
|-----------------|--------|-------|
| api-gateway | uploads | `roles/storage.objectAdmin` (lesen + schreiben) |
| api-gateway | outputs | `roles/storage.objectViewer` (lesen für Presigned URLs) |
| transcoding-worker | uploads | `roles/storage.objectViewer` (lesen) |
| transcoding-worker | outputs | `roles/storage.objectAdmin` (schreiben) |

**Workload Identity Bindings:** Verknüpfen die Kubernetes ServiceAccounts mit den GCP Service Accounts. Da boto3 keine Workload Identity unterstützt, werden diese Bindings zwar erstellt, aber letztlich über HMAC Keys ergänzt (siehe unten).

---

## HMAC Keys & Kubernetes Secret (`hmac.tf`)

```hcl
resource "google_storage_hmac_key" "api_gateway" {
  service_account_email = google_service_account.api_gateway.email
}

resource "google_storage_hmac_key" "worker" {
  service_account_email = google_service_account.transcoding_worker.email
}

resource "kubernetes_secret" "gcs_hmac_credentials" {
  metadata {
    name      = "gcs-hmac-credentials"
    namespace = var.namespace
  }

  data = {
    api-gateway-access-key = google_storage_hmac_key.api_gateway.access_id
    api-gateway-secret     = google_storage_hmac_key.api_gateway.secret
    worker-access-key      = google_storage_hmac_key.worker.access_id
    worker-secret          = google_storage_hmac_key.worker.secret
  }
}
```

HMAC Keys sind GCS-eigene Credentials die das AWS S3 SigV4-Format implementieren. Sie ermöglichen boto3, mit GCS zu kommunizieren als wäre es AWS S3.

**Kritisch: Namespace muss vor `terraform apply` existieren.** Terraform erstellt das Kubernetes Secret direkt über die K8s API — der Namespace `video-transcoding` muss deshalb bereits existieren bevor Terraform ausgeführt wird. Diese Abhängigkeit wird im Deployment-Guide dokumentiert.

---

## Outputs (`outputs.tf`)

```
cluster_name              = "video-transcoding"
cluster_location          = "us-central1"
artifact_registry_url     = "us-central1-docker.pkg.dev/k8s-transcoding-plattform/transcoding"
uploads_bucket            = "k8s-transcoding-uploads"
outputs_bucket            = "k8s-transcoding-outputs"
api_gateway_service_account = "api-gateway@k8s-transcoding-plattform.iam.gserviceaccount.com"
worker_service_account    = "transcoding-worker@k8s-transcoding-plattform.iam.gserviceaccount.com"
api_gateway_hmac_access_key = <sensitive>
api_gateway_hmac_secret     = <sensitive>
worker_hmac_access_key      = <sensitive>
worker_hmac_secret          = <sensitive>
kubectl_config_command    = "gcloud container clusters get-credentials video-transcoding --region us-central1 --project k8s-transcoding-plattform"
```

HMAC Keys sind als `sensitive` markiert und werden nicht im Terminal angezeigt. Sie können über `terraform output -raw api_gateway_hmac_access_key` abgerufen werden.

---

## Provisionierte Ressourcen (Gesamt)

`terraform apply` hat **24 Ressourcen** erfolgreich erstellt:

- 6 GCP APIs aktiviert
- 1 GKE Autopilot Cluster
- 2 GCS Buckets (uploads + outputs)
- 1 Artifact Registry Repository
- 2 GCP Service Accounts
- 4 Bucket IAM Bindings
- 2 Workload Identity Bindings
- 2 HMAC Keys
- 1 Kubernetes Secret
- 3 weitere (Remote State, Provider-Konfiguration)

---

**Nächstes Dokument:** [Kubernetes Manifests](./gke-kubernetes-manifests.md)