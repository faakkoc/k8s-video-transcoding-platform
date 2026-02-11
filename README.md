# Video Transcoding Platform on Kubernetes

Cloud-native video transcoding platform using Kubernetes, FFmpeg, and microservices architecture.

## 📋 Project Overview

This project is part of a **Scientific Project** at Hochschule RheinMain, demonstrating the benefits of Kubernetes for media technology workflows through a practical implementation of a video transcoding platform.

### Goals

1. **Learn Kubernetes** hands-on through real-world application
2. **Implement Microservices Architecture** for media processing
3. **Cloud-agnostic Design** deployable on GCP and StackIT
4. **Production-ready CI/CD** with multi-cloud support

### Use Case: Video Transcoding

- Upload videos via web interface
- Transcode to multiple formats (720p, 1080p, different codecs)
- Horizontal scaling based on workload
- Job queue management
- Download processed videos

---

## 🏗️ Architecture

### Microservices

```
┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│   Frontend   │────▶│ API Gateway │────▶│  Message     │
│   (React)    │     │  (FastAPI)  │     │  Queue       │
└──────────────┘     └─────────────┘     └──────┬───────┘
                                                 │
                                                 ▼
                                    ┌────────────────────┐
                                    │  Job Controller    │
                                    │  (K8s Jobs)        │
                                    └─────────┬──────────┘
                                              │
                                              ▼
                                    ┌─────────────────────┐
                                    │ Transcoding Workers │
                                    │ (FFmpeg + Python)   │
                                    └──────────┬──────────┘
                                               │
                                               ▼
                                    ┌──────────────────────┐
                                    │  Object Storage      │
                                    │  (Input/Output)      │
                                    └──────────────────────┘
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Container Runtime** | Docker | Application containerization |
| **Orchestration** | Kubernetes | Container management & scaling |
| **Local Dev** | Kind | Local Kubernetes cluster |
| **API Gateway** | FastAPI (Python) | REST API, job management |
| **Frontend** | React + Vite | User interface |
| **Transcoding** | FFmpeg | Video processing |
| **Message Queue** | RabbitMQ / Redis | Async job distribution |
| **Storage** | S3-compatible Object Storage | Video file storage |
| **Database** | PostgreSQL | Job metadata |
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
│   ├── frontend/                  # React UI
│   ├── api-gateway/               # FastAPI service
│   ├── job-controller/            # K8s Job manager
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

- Docker Desktop
- Kind
- kubectl
- WSL2 (if on Windows)

### Local Development

```bash
# Clone repository
git clone https://github.com/faakkoc/k8s-video-transcoding-platform.git
cd k8s-video-transcoding-platform

# Create local Kubernetes cluster
./scripts/setup-kind.sh

# Deploy services
./scripts/deploy-local.sh

# Access application
# Frontend: http://localhost:8080
# API: http://localhost:8080/api
```

## Documentation

Detailed documentation is available in the `docs/` directory:

- [Kubernetes Fundamentals](docs/01-kubernetes-fundamentals/)
- [Microservices Architecture](docs/02-microservices-architecture/)
- [Design Decisions](docs/03-design-decisions/)
- [Implementation Guide](docs/04-implementation/)
- [Deployment](docs/05-deployment/)
- [Lessons Learned](docs/06-lessons-learned/)

## Development Status

This project is currently in active development as part of an academic research project.

### Roadmap

- [x] Setup development environment
- [x] Implement API Gateway
- [ ] Implement Transcoding Worker
- [ ] Implement Frontend
- [ ] Local Kubernetes deployment
- [ ] GCP deployment
- [ ] StackIT deployment
- [ ] CI/CD pipelines
- [ ] Production hardening

---

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details

