# Video Transcoding Platform on Kubernetes

Cloud-native video transcoding platform using Kubernetes, FFmpeg, and microservices architecture.

## Project Overview

This project is part of a **Scientific Project** at Hochschule RheinMain, demonstrating the benefits of Kubernetes for media technology workflows through a practical implementation of a video transcoding platform.

### Goals

1. **Learn Kubernetes** hands-on through real-world application
2. **Implement Microservices Architecture** for media processing
3. **Cloud-agnostic Design** deployable on GCP and StackIT
4. **Production-ready CI/CD** with GitHub Actions and Workload Identity Federation

### Use Case: Video Transcoding

- Upload videos via REST API (Swagger UI)
- Transcode to multiple formats (480p, 720p, 1080p, 4k)
- Horizontal scaling based on workload
- Job queue management via Kubernetes Jobs
- Download processed videos via presigned URLs

---

## Architecture

```
Internet
    │
    ▼
┌─────────────────────────────────────────────────────┐
│              Kubernetes Cluster                     │
│                                                     │
│  ┌──────────────────┐                               │
│  │   API Gateway    │ ← LoadBalancer / Port-Forward │
│  │  (FastAPI, 2x)   │                               │
│  └────────┬─────────┘                               │
│           │ creates K8s Job                         │
│           ▼                                         │
│  ┌──────────────────┐                               │
│  │ Transcoding Job  │ (on demand, auto-scaled)      │
│  │  (FFmpeg Worker) │                               │
│  └────────┬─────────┘                               │
└───────────┼─────────────────────────────────────────┘
            │ boto3 S3-compatible API
            ▼
┌──────────────────────────────────┐
│         Object Storage           │
│  uploads bucket │ outputs bucket │
│  (MinIO / GCS)  │  (MinIO / GCS) │
└──────────────────────────────────┘
```

### Microservices

| Service | Technology | Purpose |
|---------|------------|---------|
| **API Gateway** | FastAPI (Python) | REST API, upload, job management |
| **Transcoding Worker** | FFmpeg + Python | Video transcoding |

### Technology Stack

| Component | Local (Kind) | GKE (GCP) |
|-----------|-------------|-----------|
| **Orchestration** | Kind | GKE Autopilot |
| **Object Storage** | MinIO | Google Cloud Storage |
| **Container Registry** | `kind load` | Google Artifact Registry |
| **Credentials** | Hardcoded (MinIO) | HMAC Keys (K8s Secret) |
| **Infrastructure** | Manual | Terraform |
| **CI/CD** | — | GitHub Actions + WIF |

---

## Performance (GKE Autopilot)

| Szenario | Dauer | Ursache |
|----------|-------|---------|
| **Cold Start** (erster Job nach Leerlauf) | 60–90s | Autopilot fährt neuen Node hoch |
| **Warm Start** (Node bereits laufend) | ~10–15s | Nur FFmpeg Transcoding |
| **FFmpeg Transcoding** (720p, 1MB Video) | ~9s | Reine Rechenzeit |

**Trade-off:** GKE Autopilot skaliert Nodes automatisch herunter wenn keine Last vorhanden ist — das spart Kosten, führt aber beim ersten Job nach einer Ruhephase zu 60–90 Sekunden Latenz. Für ein PoC-Projekt ist dieser Trade-off akzeptabel. Ein produktiver Einsatz würde Standard GKE mit vorprovisioniertem Node Pool nutzen.

---

## Repository Structure

```
k8s-video-transcoding-platform/
├── docs/                          # Scientific documentation
│   ├── 01-kubernetes-fundamentals/
│   ├── 02-microservices-architecture/
│   ├── 03-design-decisions/
│   ├── 04-implementation/
│   ├── 05-deployment/
│   └── 06-lessons-learned/
├── services/                      # Microservices
│   ├── api-gateway/               # FastAPI service
│   └── transcoding-worker/        # FFmpeg worker
├── kubernetes/                    # K8s manifests
│   ├── local/                     # Kind cluster
│   └── gke/                       # GKE production
├── terraform/                     # Infrastructure as Code
│   └── gcp/                       # Google Cloud
├── scripts/                       # Helper scripts
└── .github/workflows/             # CI/CD pipelines
```

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

# Deploy services
./scripts/deploy-local.sh

# Access Swagger UI
# http://localhost:8080/api/v1/docs
```

---

## Quick Start (GKE)

See [GKE Deployment Guide](docs/05-deployment/gke-e2e-test.md) for full instructions.

```bash
# 1. Provision infrastructure
cd terraform/gcp && terraform apply

# 2. Push Docker images (handled by CI/CD pipeline on push to main)

# 3. Deploy to GKE
kubectl apply -f kubernetes/gke/

# 4. Access Swagger UI
# http://<EXTERNAL-IP>/api/v1/docs
```

---

## CI/CD

The GitHub Actions pipeline runs automatically on every push to `main`:

- **Build & Test** — Lint (ruff) + Docker build
- **Deploy to GCP** — Docker push to Artifact Registry + Terraform plan

`terraform apply` is triggered **manually** via `Actions → Deploy to GCP → Run workflow → apply=true` to allow plan review before infrastructure changes.

Authentication uses **Workload Identity Federation** — no service account keys stored as secrets.

---

## Documentation

Detailed documentation is available in the `docs/` directory:

- [Kubernetes Fundamentals](docs/01-kubernetes-fundamentals/)
- [Microservices Architecture](docs/02-microservices-architecture/)
- [Design Decisions](docs/03-design-decisions/)
- [Implementation Guide](docs/04-implementation/)
- [Deployment](docs/05-deployment/)
- [Lessons Learned](docs/06-lessons-learned/)

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
