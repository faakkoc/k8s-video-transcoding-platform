# Video Transcoding Platform on Kubernetes

Cloud-native video transcoding platform using Kubernetes, FFmpeg, and microservices architecture.

## Project Overview

This project is part of a **Scientific Project** at Hochschule RheinMain, demonstrating the benefits of Kubernetes for media technology workflows through a practical implementation of a video transcoding platform.

### Goals

1. **Learn Kubernetes** hands-on through real-world application
2. **Implement Microservices Architecture** for media processing
3. **Cloud-agnostic Design** deployable on GCP and StackIT
4. **Production-ready CI/CD** with multi-cloud support

### Use Case: Video Transcoding

- Upload videos via web interface
- Transcode to multiple formats (480p, 720p, 1080p, 4k)
- Horizontal scaling based on workload
- Job status monitoring
- Download processed videos

---

## Architecture

### Microservices

```
┌──────────────┐     ┌─────────────┐
│   Frontend   │────▶│ API Gateway │
│  (optional)  │     │  (FastAPI)  │
└──────────────┘     └──────┬──────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
       Create K8s Job   MinIO S3      Job Status
              │         Object        & Download
              ▼         Storage
   ┌─────────────────────┐   ▲
   │ Transcoding Worker  │───┘
   │  (FFmpeg + Python)  │
   └─────────────────────┘
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Container Runtime** | Docker | Application containerization |
| **Orchestration** | Kubernetes | Container management & scaling |
| **Local Dev** | Kind | Local Kubernetes cluster |
| **API Gateway** | FastAPI (Python) | REST API, job management |
| **Transcoding** | FFmpeg | Video processing |
| **Object Storage** | MinIO (local) / GCS / StackIT | Video file storage |
| **IaC** | Terraform | Infrastructure provisioning |
| **CI/CD** | GitHub Actions | Automated deployment |

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
│   ├── gcp/                       # Google Cloud
│   └── stackit/                   # StackIT
├── scripts/                       # Helper scripts
└── .github/workflows/             # CI/CD pipelines
```

## Quick Start

### Prerequisites

- Docker
- Kind
- kubectl
- Helm
- Fish shell (recommended, scripts use Fish syntax)

### Local Development

```bash
# Clone repository
git clone https://github.com/faakkoc/k8s-video-transcoding-platform.git
cd k8s-video-transcoding-platform

# Create local Kubernetes cluster
./scripts/setup-kind.sh

# Build and load images
docker build -t api-gateway:latest services/api-gateway/
docker build -t transcoding-worker:latest services/transcoding-worker/
kind load docker-image api-gateway:latest --name video-transcoding
kind load docker-image transcoding-worker:latest --name video-transcoding

# Deploy MinIO
helm repo add minio https://charts.min.io/
helm install minio minio/minio --namespace video-transcoding \
  --set rootUser=minioadmin --set rootPassword=minioadmin123 \
  --set mode=standalone --set persistence.size=10Gi

# Deploy API Gateway
kubectl apply -f kubernetes/local/api-gateway/

# Access application
kubectl port-forward -n video-transcoding svc/api-gateway 8080:80
# API Docs: http://localhost:8080/api/v1/docs
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Liveness probe |
| GET | `/api/v1/ready` | Readiness probe |
| POST | `/api/v1/upload` | Upload video, create transcoding job |
| GET | `/api/v1/jobs/{job_id}` | Get job status |
| GET | `/api/v1/download/{job_id}` | Get presigned download URL |

## Documentation

Detailed documentation is available in the `docs/` directory:

- [Kubernetes Fundamentals](docs/01-kubernetes-fundamentals/)
- [Microservices Architecture](docs/02-microservices-architecture/)
- [Design Decisions](docs/03-design-decisions/)
- [Implementation Guide](docs/04-implementation/)
- [Deployment](docs/05-deployment/)
- [Lessons Learned](docs/06-lessons-learned/)

## Development Status

### Roadmap

- [x] Setup development environment
- [x] Implement API Gateway (upload, job creation, status, download)
- [x] Implement Transcoding Worker (FFmpeg + MinIO S3)
- [x] Local Kubernetes deployment (Kind + MinIO)
- [x] Job Status & Download Endpoints
- [ ] Frontend (optional — Swagger UI used for development)
- [ ] GCP deployment (GKE + Cloud Storage + Cloud SQL)
- [ ] StackIT deployment
- [ ] CI/CD pipelines (GitHub Actions)

---

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details