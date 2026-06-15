# Video Transcoding Platform auf Kubernetes

Cloud-native Video-Transcoding-Plattform mit Kubernetes, FFmpeg und Microservices-Architektur — deploybar auf **Google Cloud (GKE Autopilot)** und **StackIT (SKE)**.

## Projektübersicht

Dieses Projekt entstand im Rahmen eines **Scientific Projects** an der Hochschule RheinMain (Studiengang Advanced Media Technology). Es demonstriert anhand einer praktischen Implementierung, inwieweit Kubernetes eine cloud-agnostische Architektur für medientechnische Batch-Workloads ermöglicht — und welche provider-spezifischen Unterschiede in der Praxis bestehen bleiben.

**Forschungsfrage:**
> *Inwieweit ermöglicht Kubernetes eine cloud-agnostische Architektur für medientechnische Batch-Workloads, und welche provider-spezifischen Unterschiede bleiben in der Praxis bestehen?*

### Ziele

1. **Kubernetes praktisch erlernen** anhand einer realen Medientechnik-Anwendung
2. **Microservices-Architektur** für Video-Verarbeitung implementieren
3. **Cloud-agnostisches Design** — deployt und E2E getestet auf GCP und StackIT
4. **CI/CD** für GCP mit GitHub Actions und Workload Identity Federation

### Anwendungsfall: Video Transcoding

- Videos hochladen via REST API (Swagger UI)
- In mehrere Formate transcodieren (480p, 720p, 1080p, 4k)
- Horizontale Skalierung durch Kubernetes Jobs
- Verarbeitete Videos via Presigned/Signed URL herunterladen

---

## Architektur

```
Internet
    │
    ▼
┌─────────────────────────────────────────────────────┐
│              Kubernetes Cluster                     │
│        (GKE Autopilot  oder  StackIT SKE)           │
│                                                     │
│  ┌──────────────────┐                               │
│  │   API Gateway    │ ← LoadBalancer                │
│  │  (FastAPI, 2x)   │                               │
│  └────────┬─────────┘                               │
│           │ erstellt K8s Job                        │
│           ▼                                         │
│  ┌──────────────────┐                               │
│  │ Transcoding Job  │ (on demand, skaliert auto.)   │
│  │  (FFmpeg Worker) │                               │
│  └────────┬─────────┘                               │
└───────────┼─────────────────────────────────────────┘
            │ StorageClient-Abstraktion
            │ (GCSClient / S3Client)
            ▼
┌──────────────────────────────────┐
│         Object Storage           │
│  uploads bucket │ outputs bucket │
│  GCS (GKE) / StackIT Object      │
│  Storage / MinIO (lokal)         │
└──────────────────────────────────┘
```

Derselbe Anwendungscode läuft auf beiden Clouds. Der einzige Unterschied ist
die `STORAGE_PROVIDER`-Konfiguration (`gcs` vs. `s3`) in der ConfigMap — siehe
[`storage-abstraction.md`](docs/03-design-decisions/storage-abstraction.md).

### Microservices

| Service | Technologie | Aufgabe |
|---------|-------------|---------|
| **API Gateway** | FastAPI (Python) | REST API, Upload, Job-Verwaltung |
| **Transcoding Worker** | FFmpeg + Python | Video-Transcoding (on-demand K8s Job) |

### Technology Stack

| Komponente | Lokal (Kind) | GKE (GCP) | StackIT (SKE) |
|------------|-------------|-----------|----------------|
| **Orchestrierung** | Kind | GKE Autopilot | SKE (Node Pool `g1a.2d`) |
| **Object Storage** | MinIO | Google Cloud Storage | StackIT Object Storage (S3-kompatibel) |
| **Container Registry** | `kind load` | Google Artifact Registry | Harbor (StackIT) |
| **Storage Auth** | Hardcoded (MinIO) | Workload Identity (kein Secret) | Kubernetes Secret |
| **Registry Auth** | — | Workload Identity | Robot Account + `imagePullSecret` |
| **Infrastruktur** | Manuell | Terraform | Terraform |
| **CI/CD** | — | GitHub Actions + WIF | — (manuell) |
| **Region** | — | us-east1 (USA) | eu01 (Deutschland) |

---

## Cloud-Vergleich: GKE vs. StackIT

Beide Deployments sind end-to-end getestet (Upload → Job → Transcoding → Download).
Der systematische Vergleich ist die wissenschaftliche Kernleistung dieser Arbeit —
siehe [`stackit-deployment.md`](docs/05-deployment/stackit-deployment.md) für Details.

| Kriterium | GKE (GCP) | StackIT (SKE) |
|-----------|-----------|----------------|
| **Node-Management** | Vollautomatisch (Autopilot) | Manuell konfigurierter Node Pool |
| **Storage-Authentifizierung** | Workload Identity — kein Secret | Kubernetes Secret (Access/Secret Key) |
| **Registry-Authentifizierung** | Workload Identity | Harbor Robot Account + `imagePullSecret` |
| **CI/CD** | Vollautomatisch via WIF | Nicht implementiert (Future Work) |
| **Serverstandort / DSGVO** | USA (us-east1) | Deutschland (eu01) ✅ |
| **Cold-Start-Latenz** | 60–90s (Autopilot Node-Provisioning) | Kein Cold Start (Node Pool läuft durch) |
| **Setup-Aufwand** | Niedriger (Autopilot abstrahiert Nodes) | Höher (Node Pool, Maschinentyp, Namenslängen-Limits) |

**Kernerkenntnis:** Die `StorageClient`-Abstraktion ermöglicht Cloud-Agnostik auf
Anwendungsebene — der Code ist identisch. Auf Infrastrukturebene bleiben
provider-spezifische Unterschiede bestehen (Identity-Modell, Registry, CI/CD-Integration),
die sich nicht wegabstrahieren lassen.

---

## Performance (GKE Autopilot)

| Szenario | Dauer | Ursache |
|----------|-------|---------|
| **Cold Start** (erster Job nach Leerlauf) | 60–90s | Autopilot fährt neuen Node hoch |
| **Warm Start** (Node bereits laufend) | ~10–15s | Nur FFmpeg-Transcoding |
| **FFmpeg-Transcoding** (720p, 1MB Video) | ~9s | Reine Rechenzeit |

Auf StackIT (SKE mit festem Node Pool) kein Cold Start beobachtet — Job lief
direkt durch (~13s gesamt, davon ~1.5s FFmpeg).

---

## Repository-Struktur

```
k8s-video-transcoding-platform/
├── docs/                          # Wissenschaftliche Dokumentation
│   ├── 01-kubernetes-fundamentals/
│   ├── 03-design-decisions/
│   ├── 04-implementation/
│   ├── 05-deployment/             # inkl. gke-*.md und stackit-deployment.md
│   └── 06-lessons-learned/
├── services/                      # Microservices
│   ├── api-gateway/               # FastAPI Service
│   └── transcoding-worker/        # FFmpeg Worker
├── kubernetes/                    # K8s Manifests
│   ├── local/                     # Kind Cluster (MinIO)
│   ├── gke/                       # GKE Production (Workload Identity)
│   └── stackit/                   # StackIT Production (SKE, Harbor)
├── terraform/                     # Infrastructure as Code
│   ├── gcp/                       # Google Cloud (GKE, IAM, WIF)
│   └── stackit/                   # StackIT (SKE, Object Storage)
├── scripts/                       # Hilfsskripte
└── .github/workflows/             # CI/CD Pipelines (GCP)
```

Vollständige Struktur inkl. aller Dateien: siehe [`STRUCTURE.md`](STRUCTURE.md).

---

## Quick Start (Lokal)

### Voraussetzungen

- Docker
- Kind
- kubectl

```bash
# Repository klonen
git clone https://github.com/faakkoc/k8s-video-transcoding-platform.git
cd k8s-video-transcoding-platform

# Lokalen Kubernetes-Cluster erstellen
./scripts/setup-kind.sh

# Manifeste deployen (MinIO + API Gateway)
kubectl apply -f kubernetes/local/

# Swagger UI
# http://localhost:8080/api/v1/docs
```

---

## Quick Start (GKE)

Vollständige Anleitung: [`docs/05-deployment/gke-deployment.md`](docs/05-deployment/gke-deployment.md)

```bash
# 1. Infrastruktur provisionieren
cd terraform/gcp && terraform apply

# 2. Credentials holen (nach jedem terraform apply neu)
gcloud container clusters get-credentials video-transcoding \
  --region us-east1 --project k8s-transcoding-plattform

# 3. Docker Images via CI/CD-Pipeline pushen (oder manuell)

# 4. Auf GKE deployen
kubectl apply -f kubernetes/gke/

# 5. Swagger UI
# http://<EXTERNAL-IP>/api/v1/docs
```

---

## Quick Start (StackIT)

Vollständige Anleitung: [`docs/05-deployment/stackit-deployment.md`](docs/05-deployment/stackit-deployment.md)

```bash
# 1. Infrastruktur provisionieren
cd terraform/stackit && terraform apply

# 2. kubeconfig holen (30 Tage gültig)
stackit ske kubeconfig create v-tc \
  --project-id <project-id> --expiration 30d
kubectl config use-context v-tc

# 3. Docker Images manuell zu Harbor pushen

# 4. Auf StackIT deployen (inkl. Secrets — Details in stackit-deployment.md)
kubectl apply -f kubernetes/stackit/

# 5. Swagger UI
# http://<EXTERNAL-IP>/api/v1/docs
```

---

## CI/CD

Die GitHub Actions Pipeline für **GCP** läuft automatisch bei jedem Push auf `main`:

- **Build & Test** — Lint (ruff) + Docker Build
- **Deploy to GCP** — Docker Push zur Artifact Registry + Terraform Plan

`terraform apply` wird **manuell** via `Actions → Deploy to GCP → Run workflow → apply=true`
getriggert. Authentifizierung über **Workload Identity Federation** — kein Service Account Key.

Für **StackIT** existiert aktuell keine Pipeline — StackIT bietet kein WIF-Äquivalent.
Als bewusste Scoping-Entscheidung dokumentiert (Future Work).

---

## Dokumentation

- [Kubernetes Fundamentals](docs/01-kubernetes-fundamentals/)
- [Design-Entscheidungen](docs/03-design-decisions/) — inkl. StorageClient-Abstraktion
- [Implementierung](docs/04-implementation/)
- [Deployment](docs/05-deployment/) — GKE und StackIT
- [Lessons Learned](docs/06-lessons-learned/)

Vollständige Projektstruktur: [`STRUCTURE.md`](STRUCTURE.md)

---

## Lizenz

Apache License 2.0 — siehe [LICENSE](LICENSE).