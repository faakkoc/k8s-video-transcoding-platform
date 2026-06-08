# StackIT Deployment

**Datum:** 08.06.2026
**Status:** ✅ End-to-End Test erfolgreich

---

## Übersicht

Das StackIT Deployment demonstriert die Cloud-Agnostik der Plattform. Derselbe
Anwendungscode der auf GKE läuft, wird hier auf der europäischen StackIT Cloud
deployed — ohne Code-Änderungen, nur mit anderer Konfiguration.

---

## Architektur-Vergleich GCP vs. StackIT

| Komponente | GCP (GKE) | StackIT (SKE) |
|------------|-----------|---------------|
| **Kubernetes** | GKE Autopilot | SKE (StackIT Kubernetes Engine) |
| **Object Storage** | Google Cloud Storage | StackIT Object Storage (S3-kompatibel) |
| **Storage Auth** | Workload Identity (kein Secret) | Service Account Credentials (Kubernetes Secret) |
| **Storage Client** | GCSClient (google-cloud-storage) | S3Client (boto3) |
| **Container Registry** | Google Artifact Registry | StackIT Harbor Registry |
| **Registry Auth** | Workload Identity | Robot Account + Image Pull Secret |
| **Terraform Provider** | `hashicorp/google` | `stackitcloud/stackit` |
| **CI/CD Auth** | Workload Identity Federation | Service Account Key (manuell) |
| **Terraform State** | GCS Bucket (us-east1) | StackIT Object Storage (eu01) |
| **Node Management** | Vollautomatisch (Autopilot) | Node Pools manuell konfiguriert |
| **Region** | us-east1 (USA) | eu01 (Europa/Deutschland) |
| **DSGVO** | Google (USA) | Schwarz IT (Deutschland) ✅ |

---

## Warum kein Workload Identity auf StackIT?

StackIT bietet kein Workload Identity Konzept — es gibt keinen Mechanismus
womit ein Kubernetes Pod sich automatisch bei StackIT Object Storage
authentifizieren kann. Credentials müssen explizit als Kubernetes Secret
hinterlegt werden.

Dies ist ein konkreter Cloud-Architektur-Unterschied: GCP bietet mit Workload
Identity eine sicherere, credentials-freie Authentifizierung. Auf StackIT wird
ein Kubernetes Secret mit den Object Storage Credentials benötigt.

Der Kompromiss: `StorageClient`-Abstraktion mit `STORAGE_PROVIDER`-ENV-Variable:
- `gcs` für GCP → Workload Identity, kein Secret
- `s3` für StackIT → Credentials via Kubernetes Secret

---

## Bootstrap: Manuelle Schritte (Henne-Ei-Problem)

Analog zu GCP müssen einige Ressourcen manuell erstellt werden bevor
Terraform ausgeführt werden kann:

| Ressource | Erstellt via | Begründung |
|-----------|-------------|------------|
| Service Account + Key (JSON) | StackIT Portal | Terraform braucht Credentials |
| Owner-Rolle für Service Account | StackIT Portal (durch Prof.) | Ohne Owner kann Terraform keine Ressourcen erstellen |
| Terraform State Bucket | StackIT Portal | Henne-Ei-Problem |
| State Bucket Credentials | StackIT Portal → Object Storage → Credentials & Groups → Default Gruppe → Create credentials | Für S3-Backend Zugriff |
| Harbor Registry Projekt | StackIT Portal → Container Registry → Neues Projekt | Terraform unterstützt Harbor nicht direkt |
| Robot Account (Push + Pull) | Harbor Portal → Projekt → Robot-Account | **Push UND Pull Permissions nötig!** |

> **Wichtig:** Robot Account braucht sowohl Push- als auch Pull-Permissions.
> Nur Pull reicht nicht — beim Image-Push schlägt es sonst fehl.

---

## Cluster-Konfiguration

### Maschinentyp: `g1a.2d`

- 2 vCPU, 8 GB RAM
- AMD-basiert (x86/amd64 — kompatibel mit unseren Docker Images)
- General Purpose — geeignet für API Gateway + FFmpeg Worker
- Günstigste sinnvolle Option für gemischte Workloads

**Warum nicht `g1.2` oder `c1.2`?**
- `g1.2` ist deprecated und kann nicht für neue Cluster verwendet werden
- `c1.2` hat nur 4 GB RAM — zu wenig für API Gateway + Worker + System-Pods gleichzeitig
- `g1r.2d` ist ARM-basiert — inkompatibel mit amd64 Docker Images

### Kubernetes Version: `1.33`

Aktuellste supported Version zum Zeitpunkt des Deployments.

### Cluster-Name: `v-tc`

**Maximale Länge: 11 Zeichen** — StackIT API-Einschränkung.

### Node Pool-Name: `tc-pool`

**Maximale Länge: 15 Zeichen** — StackIT API-Einschränkung.

---

## Voraussetzungen

```fish
# StackIT CLI installieren (Homebrew)
brew install stackit

# Service Account Key ENV setzen
set -x STACKIT_SERVICE_ACCOUNT_KEY_PATH ~/.stackit/service-account-key.json

# State Bucket Credentials (aus Portal)
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
- SKE Kubernetes Cluster (`v-tc`, Node Pool `tc-pool`, Maschinentyp `g1a.2d`)
- Object Storage Buckets (`k8s-transcoding-uploads`, `k8s-transcoding-outputs`)
- Object Storage Credentials Group + Credentials (Access Key + Secret Key)

**Dauer:** ~5-10 Minuten

---

## Phase 2: Container Registry — Images pushen

```fish
# Bei Harbor Registry einloggen
docker login registry.onstackit.cloud

# API Gateway bauen und pushen
docker build -t registry.onstackit.cloud/video-transcoding/api-gateway:latest \
  services/api-gateway/
docker push registry.onstackit.cloud/video-transcoding/api-gateway:latest

# Transcoding Worker bauen und pushen
docker build -t registry.onstackit.cloud/video-transcoding/transcoding-worker:latest \
  services/transcoding-worker/
docker push registry.onstackit.cloud/video-transcoding/transcoding-worker:latest
```

---

## Phase 3: kubectl konfigurieren

```fish
# kubeconfig für SKE Cluster holen (30 Tage gültig)
stackit ske kubeconfig create v-tc \
  --project-id f137b33f-56c2-463a-b97b-a3dc37447902 \
  --expiration 30d

# Context wechseln
kubectl config use-context v-tc

# Cluster prüfen
kubectl get nodes
```

> **Hinweis:** Nach jedem `terraform destroy` und erneutem `apply` muss die
> kubeconfig neu geholt werden — das Cluster-Zertifikat ändert sich.

---

## Phase 4: Kubernetes Manifests anwenden

```fish
# Namespace
kubectl apply -f kubernetes/stackit/00-namespace.yaml

# ConfigMap
kubectl apply -f kubernetes/stackit/01-configmap.yaml

# S3 Credentials Secret (aus Terraform Output)
kubectl create secret generic s3-credentials \
  --from-literal=access-key=$(cd terraform/stackit && terraform output -raw object_storage_access_key) \
  --from-literal=secret-key=$(cd terraform/stackit && terraform output -raw object_storage_secret_key) \
  -n video-transcoding \
  --dry-run=client -o yaml | kubectl apply -f -

# Harbor Pull Secret
# Wichtig: Username mit einfachen Anführungszeichen wegen $ in Fish Shell
kubectl create secret docker-registry harbor-pull-secret \
  --docker-server=registry.onstackit.cloud \
  --docker-username='robot$video-transcoding+skepull' \
  --docker-password=<robot-account-token> \
  -n video-transcoding

# Service Accounts + RBAC
kubectl apply -f kubernetes/stackit/03-service-accounts.yaml

# API Gateway
kubectl apply -f kubernetes/stackit/api-gateway/
```

---

## Phase 5: End-to-End Test

```fish
# External IP ermitteln
kubectl get svc -n video-transcoding

# Pods prüfen
kubectl get pods -n video-transcoding

# Swagger UI
# http://<EXTERNAL-IP>/api/v1/docs

# Job Status prüfen
curl http://<EXTERNAL-IP>/api/v1/jobs/<JOB_ID>

# Download URL generieren
curl http://<EXTERNAL-IP>/api/v1/download/<JOB_ID>
```

---

## Infrastruktur herunterfahren (Kostensparen)

```fish
# Nur SKE Cluster löschen
cd terraform/stackit
terraform destroy -target=stackit_ske_cluster.main
```

Object Storage Buckets und Credentials bleiben erhalten.

> **Nach erneutem `terraform apply`:** kubeconfig neu holen, alle Kubernetes
> Ressourcen neu anwenden (Namespace, ConfigMap, Secrets, Service Accounts,
> Deployment) — der Cluster verliert alle Kubernetes-Ressourcen beim Destroy.

---

## Bekannte Limitierungen & Offene Punkte

### 1. Kein CI/CD für StackIT

GCP hat eine vollautomatische GitHub Actions Pipeline. Für StackIT gibt es
aktuell keine CI/CD — Images müssen manuell gebaut und gepusht werden.

StackIT unterstützt kein Workload Identity Federation → Service Account Key
müsste als GitHub Secret hinterlegt werden. Das ist ein Schritt zurück
gegenüber GCP (kein langlebiger Key als Secret), aber für ein PoC akzeptabel.

### 2. IMAGE_PULL_SECRET manuell gepatcht

Das `IMAGE_PULL_SECRET` für Worker-Jobs wurde beim ersten Deployment per
`kubectl patch` nachträglich hinzugefügt. Beim nächsten Deployment ist es
bereits in `deployment.yaml` enthalten.

### 3. Kubernetes Ressourcen gehen beim Cluster-Destroy verloren

Anders als bei GCP (wo Terraform State Buckets und IAM erhalten bleiben)
müssen nach jedem `terraform destroy -target=stackit_ske_cluster.main`
alle Kubernetes Ressourcen neu deployed werden.

---

## Challenges & Learnings

| Problem | Ursache | Lösung |
|---------|---------|--------|
| Cluster-Name zu lang | StackIT: max. 11 Zeichen | `v-tc` statt `video-transcoding` |
| Node Pool-Name zu lang | StackIT: max. 15 Zeichen | `tc-pool` |
| `g1.2` deprecated | Ältere Maschinengeneration | `g1a.2d` (AMD, aktuell) |
| `g1r.2d` inkompatibel | ARM-Architektur, Images sind amd64 | `g1a.2d` (x86/AMD) |
| Robot Account Pull fehlgeschlagen | Nur Pull-Permission, kein Push | Push + Pull Permissions für Robot Account |
| Registry URL falsch | `registry.eu01.onstackit.cloud` existiert nicht | `registry.onstackit.cloud` |
| Fish Shell `$` in Username | `robot$video-transcoding+skepull` wird als Variable interpretiert | Einfache Anführungszeichen: `'robot$...'` |
| Worker ImagePullBackOff | `imagePullSecrets` fehlte im dynamisch erstellten Job | `IMAGE_PULL_SECRET` ENV-Variable in `k8s_client.py` |
| kubeconfig abgelaufen | Cluster neu erstellt, altes Zertifikat ungültig | `stackit ske kubeconfig create v-tc` erneut ausführen |