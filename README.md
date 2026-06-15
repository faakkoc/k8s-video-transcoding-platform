# Video Transcoding Platform on Kubernetes

Cloud-native video transcoding platform using Kubernetes, FFmpeg, and microservices architecture — deployable on **Google Cloud (GKE Autopilot)** and **StackIT (SKE)**.

## Project Overview

This project is part of a **Scientific Project** at Hochschule RheinMain, demonstrating the benefits of Kubernetes for media technology workflows through a practical implementation of a video transcoding platform.

### Goals

1. **Learn Kubernetes** hands-on through real-world application
2. **Implement Microservices Architecture** for media processing
3. **Cloud-agnostic Design** — deployed and end-to-end tested on both GCP and StackIT
4. **Production-ready CI/CD** for GCP, with GitHub Actions and Workload Identity Federation

### Use Case: Video Transcoding

- Upload videos via REST API (Swagger UI)
- Transcode to multiple formats (480p, 720p, 1080p, 4k)
- Horizontal scaling based on workload
- Job queue management via Kubernetes Jobs
- Download processed videos via presigned/signed URLs

---

## Architecture

```
Internet
    │
    ▼
┌─────────────────────────────────────────────────────┐
│              Kubernetes Cluster                     │
│        (GKE Autopilot  or  StackIT SKE)             │
│                                                     │
│  ┌──────────────────┐                               │
│  │   API Gateway    │ ← LoadBalancer                │
│  │  (FastAPI, 2x)   │                               │
│  └────────┬─────────┘                               │
│           │ creates K8s Job                         │
│           ▼                                         │
│  ┌──────────────────┐                               │
│  │ Transcoding Job  │ (on demand, auto-scaled)      │
│  │  (FFmpeg Worker) │                               │
│  └────────┬─────────┘                               │
└───────────┼─────────────────────────────────────────┘
            │ StorageClient abstraction
            │ (GCSClient / S3Client)
            ▼
┌──────────────────────────────────┐
│         Object Storage           │
│  uploads bucket │ outputs bucket │
│  GCS (GKE) / StackIT Object      │
│  Storage / MinIO (lokal)         │
└──────────────────────────────────┘
```

Derselbe Anwendungscode läuft auf beiden Clouds — der einzige Unterschied ist
die `STORAGE_PROVIDER`-Konfiguration (`gcs` vs. `s3`), siehe
[`storage-abstraction.md`](docs/03-design-decisions/storage-abstraction.md).

### Microservices

| Service | Technology | Purpose |
|---------|------------|---------|
| **API Gateway** | FastAPI (Python) | REST API, upload, job management |
| **Transcoding Worker** | FFmpeg + Python | Video transcoding (on-demand K8s Job) |

### Technology Stack

| Component | Local (Kind) | GKE (GCP) | StackIT (SKE) |
|-----------|-------------|-----------|----------------|
| **Orchestration** | Kind | GKE Autopilot | SKE (Node Pool `g1a.2d`) |
| **Object Storage** | MinIO | Google Cloud Storage | StackIT Object Storage (S3-kompatibel) |
| **Container Registry** | `kind load` | Google Artifact Registry | Harbor (StackIT) |
| **Storage Auth** | Hardcoded (MinIO) | Workload Identity (kein Secret) | Kubernetes Secret (Access/Secret Key) |
| **Registry Auth** | — | Workload Identity | Robot Account + `imagePullSecret` |
| **Infrastructure** | Manual | Terraform | Terraform |
| **CI/CD** | — | GitHub Actions + WIF | — (manuell, siehe unten) |
| **Region** | — | us-east1 (USA) | eu01 (Deutschland) |

---

## Cloud-Vergleich: GKE vs. StackIT

Beide Deployments sind end-to-end getestet (Upload → Job → Transcoding →
Download). Der Vergleich ist der wissenschaftliche Kern dieser Arbeit — siehe
[`stackit-deployment.md`](docs/05-deployment/stackit-deployment.md) für Details.

| Kriterium | GKE (GCP) | StackIT (SKE) |
|-----------|-----------|----------------|
| **Node-Management** | Vollautomatisch (Autopilot) | Manuell konfigurierter Node Pool |
| **Storage-Authentifizierung** | Workload Identity — kein Secret im Cluster | Kubernetes Secret mit Access/Secret Key |
| **Registry-Authentifizierung** | Workload Identity | Harbor Robot Account + `imagePullSecret` |
| **CI/CD** | Vollautomatisch via WIF (keine Keys als Secret) | Nicht implementiert — Service Account Key wäre nötig |
| **Datenschutz / Serverstandort** | USA (us-east1) | Deutschland (eu01) — DSGVO-Vorteil |
| **Setup-Aufwand (gefühlt)** | Niedriger (Autopilot abstrahiert Nodes) | Höher (Node Pool, Maschinentyp, Namenslängen-Limits) |
| **Cold-Start-Latenz** | 60–90s (Autopilot Node-Provisioning) | Kein Cold Start beobachtet (Node Pool läuft durchgehend) |

**Kernerkenntnis:** Die `StorageClient`-Abstraktion ermöglicht echte
Cloud-Agnostik auf Anwendungsebene — der Code ist identisch. Auf
Infrastruktur-Ebene bleiben jedoch provider-spezifische Unterschiede bestehen,
die sich nicht wegabstrahieren lassen (Identity-Modell, Registry, CI/CD-Integration).

---

## Performance (GKE Autopilot)

| Szenario | Dauer | Ursache |
|----------|-------|---------|
| **Cold Start** (erster Job nach Leerlauf) | 60–90s | Autopilot fährt neuen Node hoch |
| **Warm Start** (Node bereits laufend) | ~10–15s | Nur FFmpeg Transcoding |
| **FFmpeg Transcoding** (720p, 1MB Video) | ~9s | Reine Rechenzeit |

**Trade-off:** GKE Autopilot skaliert Nodes automatisch herunter, wenn keine
Last vorhanden ist — das spart Kosten, führt aber beim ersten Job nach einer
Ruhephase zu 60–90 Sekunden Latenz. Für ein PoC-Projekt ist dieser Trade-off
akzeptabel. Ein produktiver Einsatz würde Standard GKE mit vorprovisioniertem
Node Pool nutzen.

Auf StackIT (SKE mit festem Node Pool) wurde im E2E-Test kein vergleichbarer
Cold Start beobachtet — der Job lief direkt (~13s gesamt, davon ~1.5s FFmpeg).

---

## Repository Structure

```
k8s-video-transcoding-platform/
├── docs/                          # Scientific documentation
│   ├── 01-kubernetes-fundamentals/
│   ├── 03-design-decisions/
│   ├── 04-implementation/
│   ├── 05-deployment/             # inkl. gke-*.md und stackit-deployment.md
│   └── 06-lessons-learned/
├── services/                      # Microservices
│   ├── api-gateway/               # FastAPI service
│   └── transcoding-worker/        # FFmpeg worker
├── kubernetes/                    # K8s manifests
│   ├── local/                     # Kind cluster (MinIO)
│   ├── gke/                       # GKE production (Workload Identity)
│   └── stackit/                   # StackIT production (SKE, Harbor)
├── terraform/                     # Infrastructure as Code
│   ├── gcp/                       # Google Cloud (GKE, IAM, WIF)
│   └── stackit/                   # StackIT (SKE, Object Storage)
├── scripts/                       # Helper scripts
└── .github/workflows/             # CI/CD pipelines (GCP)
```

Vollständige Struktur inkl. aller Dateien: siehe [`STRUCTURE.md`](STRUCTURE.md).

---

## Quick Start (Local)

### Prerequisites

- Docker
- Kind
- kubectl

### Local Development

```bash
# Clone repository
git clone https://github.com/faakkoc/k8s-video-transcoding-platform.git
cd k8s-video-transcoding-platform

# Create local Kubernetes cluster
./scripts/setup-kind.sh

# Deploy manifests (MinIO + API Gateway)
kubectl apply -f kubernetes/local/

# Access Swagger UI
# http://localhost:8080/api/v1/docs
```

---

## Quick Start (GKE)

Vollständige Anleitung: [`docs/05-deployment/gke-deployment.md`](docs/05-deployment/gke-deployment.md)

```bash
# 1. Provision infrastructure
cd terraform/gcp && terraform apply

# 2. Get credentials (nach jedem terraform apply neu nötig)
gcloud container clusters get-credentials video-transcoding \
  --region us-east1 --project k8s-transcoding-plattform

# 3. Push Docker images (oder via CI/CD-Pipeline)

# 4. Deploy to GKE
kubectl apply -f kubernetes/gke/

# 5. Access Swagger UI
# http://<EXTERNAL-IP>/api/v1/docs
```

---

## Quick Start (StackIT)

Vollständige Anleitung: [`docs/05-deployment/stackit-deployment.md`](docs/05-deployment/stackit-deployment.md)

```bash
# 1. Provision infrastructure
cd terraform/stackit && terraform apply

# 2. Get kubeconfig (30 Tage gültig)
stackit ske kubeconfig create v-tc \
  --project-id <project-id> --expiration 30d
kubectl config use-context v-tc

# 3. Push Docker images to Harbor (manuell)

# 4. Deploy to StackIT (Namespace, ConfigMap, Secrets, ServiceAccounts, Deployment)
kubectl apply -f kubernetes/stackit/

# 5. Access Swagger UI
# http://<EXTERNAL-IP>/api/v1/docs
```

> **Hinweis:** S3-Credentials-Secret und Harbor `imagePullSecret` müssen vor
> Schritt 4 separat erstellt werden (aus Terraform-Output bzw. Robot-Account-Token)
> — Details in `stackit-deployment.md`.

---

## CI/CD

Die GitHub Actions Pipeline für **GCP** läuft automatisch bei jedem Push auf `main`:

- **Build & Test** — Lint (ruff) + Docker build
- **Deploy to GCP** — Docker push zur Artifact Registry + Terraform plan

`terraform apply` wird **manuell** via `Actions → Deploy to GCP → Run workflow
→ apply=true` getriggert, um Plan-Review vor Infrastruktur-Änderungen zu ermöglichen.

Authentifizierung läuft über **Workload Identity Federation** — keine Service
Account Keys als Secrets.

**StackIT:** Aktuell keine CI/CD-Pipeline. StackIT bietet kein WIF-Äquivalent —
ein Service Account Key müsste als GitHub Secret hinterlegt werden. Als
bewusste Scoping-Entscheidung dokumentiert (Future Work).

---

## Documentation

Detailed documentation is available in the `docs/` directory:

- [Kubernetes Fundamentals](docs/01-kubernetes-fundamentals/)
- [Design Decisions](docs/03-design-decisions/) — inkl. StorageClient-Abstraktion
- [Implementation Guide](docs/04-implementation/)
- [Deployment](docs/05-deployment/) — GKE und StackIT
- [Lessons Learned](docs/06-lessons-learned/)

Vollständige Projektstruktur: [`STRUCTURE.md`](STRUCTURE.md)

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.