# StackIT Deployment

**Datum:** 27.05.2026
**Status:** In Bearbeitung

---

## Übersicht

Das StackIT Deployment demonstriert die Cloud-Agnostik der Plattform. Derselbe
Anwendungscode der auf GKE läuft, wird hier auf der europäischen StackIT Cloud
deployed — ohne Code-Änderungen, nur mit anderer Konfiguration.

### Architektur-Vergleich GCP vs. StackIT

| Komponente | GCP (GKE) | StackIT (SKE) |
|------------|-----------|---------------|
| **Kubernetes** | GKE Autopilot | SKE (StackIT Kubernetes Engine) |
| **Object Storage** | Google Cloud Storage | StackIT Object Storage (S3-kompatibel) |
| **Storage Auth** | Workload Identity (kein Secret) | Service Account Credentials (Kubernetes Secret) |
| **Storage Client** | GCSClient (google-cloud-storage) | S3Client (boto3) |
| **Container Registry** | Google Artifact Registry | StackIT Container Registry |
| **Terraform Provider** | `hashicorp/google` | `stackitcloud/stackit` |
| **CI/CD Auth** | Workload Identity Federation | Service Account Key (GitHub Secret) |
| **Terraform State** | GCS Bucket (us-east1) | StackIT Object Storage (eu01) |
| **Region** | us-east1 (USA) | eu01 (Europa) |
| **DSGVO** | Google (USA) | StackIT/Schwarz IT (Deutschland) ✅ |

### Warum kein Workload Identity auf StackIT?

StackIT bietet kein Workload Identity Konzept — es gibt keinen Mechanismus
womit ein Kubernetes Pod sich automatisch bei StackIT Object Storage
authentifizieren kann. Credentials müssen explizit als Kubernetes Secret
hinterlegt werden.

Dies ist ein konkreter Cloud-Architektur-Unterschied der in der wissenschaftlichen
Ausarbeitung diskutiert wird: GCP bietet mit Workload Identity eine sicherere,
credentials-freie Authentifizierung die StackIT (noch) nicht unterstützt.

Der Kompromiss: `StorageClient`-Abstraktion mit `STORAGE_PROVIDER`-ENV-Variable —
`gcs` für GCP (Workload Identity), `s3` für StackIT (Credentials via Secret).

---

## Bootstrap: Manuelle Schritte (Henne-Ei-Problem)

Analog zu GCP müssen einige Ressourcen manuell erstellt werden bevor
Terraform ausgeführt werden kann:

| Ressource | Erstellt via | Begründung |
|-----------|-------------|------------|
| Service Account + Key | StackIT Portal | Terraform braucht Credentials |
| Terraform State Bucket | StackIT Portal | Terraform kann seinen eigenen State-Bucket nicht selbst anlegen |
| State Bucket Credentials | StackIT Portal | Für S3-Backend Zugriff |

Alles weitere (SKE Cluster, Buckets, Storage Credentials) erstellt Terraform automatisch.

---

## Voraussetzungen

```fish
# StackIT CLI installieren (für kubeconfig)
# https://github.com/stackitcloud/stackit-cli

# Terraform ENV-Variablen setzen
set -x STACKIT_SERVICE_ACCOUNT_KEY_PATH /path/to/service-account-key.json

# State Bucket Credentials
set -x AWS_ACCESS_KEY_ID <state-bucket-access-key>
set -x AWS_SECRET_ACCESS_KEY <state-bucket-secret-key>
```

---

## Phase 1: Terraform Apply

```fish
cd terraform/stackit
terraform init
terraform plan
terraform apply
```

Erstellt:
- SKE Kubernetes Cluster (`video-transcoding`)
- Object Storage Buckets (`k8s-transcoding-uploads`, `k8s-transcoding-outputs`)
- Object Storage Credentials (Access Key + Secret Key)

---

## Phase 2: Container Registry & Images

```fish
# Bei StackIT Container Registry anmelden
docker login registry.eu01.onstackit.cloud

# API Gateway bauen und pushen
docker build -t registry.eu01.onstackit.cloud/video-transcoding/api-gateway:latest \
  services/api-gateway/
docker push registry.eu01.onstackit.cloud/video-transcoding/api-gateway:latest

# Transcoding Worker bauen und pushen
docker build -t registry.eu01.onstackit.cloud/video-transcoding/transcoding-worker:latest \
  services/transcoding-worker/
docker push registry.eu01.onstackit.cloud/video-transcoding/transcoding-worker:latest
```

---

## Phase 3: kubectl konfigurieren

```fish
# StackIT CLI für kubeconfig nutzen
stackit ske kubeconfig create \
  --project-id f137b33f-56c2-463a-b97b-a3dc37447902 \
  --cluster-name video-transcoding
```

---

## Phase 4: Kubernetes Manifests anwenden

```fish
# Namespace
kubectl apply -f kubernetes/stackit/00-namespace.yaml

# ConfigMap
kubectl apply -f kubernetes/stackit/01-configmap.yaml

# Secret erstellen (Credentials aus Terraform Output)
kubectl create secret generic s3-credentials \
  --from-literal=access-key=$(cd terraform/stackit && terraform output -raw object_storage_access_key) \
  --from-literal=secret-key=$(cd terraform/stackit && terraform output -raw object_storage_secret_key) \
  -n video-transcoding \
  --dry-run=client -o yaml | kubectl apply -f -

# Service Accounts & RBAC
kubectl apply -f kubernetes/stackit/03-service-accounts.yaml

# API Gateway
kubectl apply -f kubernetes/stackit/api-gateway/
```

---

## Phase 5: End-to-End Test

```fish
# External IP ermitteln
kubectl get svc -n video-transcoding

# Swagger UI öffnen
# http://<EXTERNAL-IP>/api/v1/docs

# Video hochladen und Job status prüfen
curl -X POST http://<EXTERNAL-IP>/api/v1/upload \
  -F "file=@/tmp/test-video.mp4" \
  -F "preset=720p"
```

---

## Infrastruktur herunterfahren (Kostensparen)

```fish
# Nur SKE Cluster löschen — Buckets und Credentials bleiben
cd terraform/stackit
terraform destroy -target=stackit_ske_cluster.main
```

---

## Unterschiede zum GCP Deployment

### 1. Secret Management

GCP nutzt Workload Identity — kein Secret im Cluster. StackIT benötigt
ein Kubernetes Secret mit den Object Storage Credentials. Das Secret wird
aus dem Terraform Output erstellt und ist damit reproduzierbar.

### 2. Container Registry

StackIT hat eine eigene Container Registry (`registry.eu01.onstackit.cloud`).
Die Images müssen separat gepusht werden — anders als bei GCP wo die CI/CD
Pipeline das automatisch übernimmt.

### 3. Node Pools

Im Gegensatz zu GKE Autopilot (fully managed, keine Node-Konfiguration)
müssen bei SKE Node Pools explizit definiert werden. Das gibt mehr Kontrolle,
erfordert aber auch mehr Konfiguration.

### 4. DSGVO-Konformität

StackIT betreibt Rechenzentren in Deutschland (Schwarz IT / Lidl/Kaufland Gruppe).
Alle Daten bleiben in der EU — ein wesentlicher Vorteil gegenüber GCP (USA).

---

**Nächstes Dokument:** [CI/CD für StackIT](./cicd-stackit.md) (geplant)