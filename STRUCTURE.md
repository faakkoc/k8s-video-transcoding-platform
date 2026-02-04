# Projektstruktur

Diese Datei dokumentiert die Ordnerstruktur des Projekts.

```
k8s-video-transcoding-platform/
│
├── .gitignore                     # Git ignore rules
├── LICENSE                        # Apache 2.0 License
├── README.md                      # Project overview
│
├── docs/                          # Scientific documentation
│   ├── README.md                  # Documentation overview
│   │
│   ├── 01-kubernetes-fundamentals/
│   │   ├── container-orchestration.md
│   │   ├── kubernetes-architecture.md
│   │   └── core-concepts.md
│   │
│   ├── 02-microservices-architecture/
│   │   ├── monolith-vs-microservices.md
│   │   ├── service-patterns.md
│   │   └── media-workflows.md
│   │
│   ├── 03-design-decisions/
│   │   ├── architecture-overview.md
│   │   ├── technology-stack.md
│   │   └── cloud-agnostic-design.md
│   │
│   ├── 04-implementation/
│   │   ├── development-setup.md
│   │   ├── api-gateway.md
│   │   ├── transcoding-worker.md
│   │   └── kubernetes-manifests.md
│   │
│   ├── 05-deployment/
│   │   ├── local-kind.md
│   │   ├── gke-deployment.md
│   │   ├── stackit-deployment.md
│   │   └── cicd-pipelines.md
│   │
│   └── 06-lessons-learned/
│       ├── kubernetes-benefits.md
│       ├── challenges.md
│       └── production-readiness.md
│
├── services/                      # Microservices Source Code
│   │
│   ├── frontend/                  # React Frontend
│   │   ├── src/
│   │   ├── public/
│   │   ├── Dockerfile
│   │   ├── package.json
│   │   └── README.md
│   │
│   ├── api-gateway/               # FastAPI Gateway
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── routers/
│   │   │   ├── models/
│   │   │   └── utils/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── README.md
│   │
│   ├── job-controller/            # Kubernetes Job Controller
│   │   ├── controller.py
│   │   ├── k8s_client.py
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── README.md
│   │
│   └── transcoding-worker/        # FFmpeg Transcoding Worker
│       ├── worker.py
│       ├── ffmpeg_presets.py
│       ├── Dockerfile
│       ├── requirements.txt
│       └── README.md
│
├── kubernetes/                    # Kubernetes Manifests
│   │
│   ├── local/                     # Kind (local development)
│   │   ├── 00-namespace.yaml
│   │   ├── 01-configmap.yaml
│   │   ├── 02-secrets.yaml
│   │   ├── frontend/
│   │   │   ├── deployment.yaml
│   │   │   ├── service.yaml
│   │   │   └── ingress.yaml
│   │   ├── api-gateway/
│   │   │   ├── deployment.yaml
│   │   │   ├── service.yaml
│   │   │   └── hpa.yaml
│   │   ├── job-controller/
│   │   │   ├── deployment.yaml
│   │   │   └── service.yaml
│   │   └── transcoding-worker/
│   │       └── job-template.yaml
│   │
│   └── gke/                       # GKE Production
│       ├── 00-namespace.yaml
│       ├── 01-configmap.yaml
│       ├── 02-secrets.yaml
│       └── ... (similar to local/)
│
├── terraform/                     # Infrastructure as Code
│   │
│   ├── gcp/                       # Google Cloud Platform
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── gke.tf
│   │   ├── storage.tf
│   │   ├── pubsub.tf
│   │   └── sql.tf
│   │
│   └── stackit/                   # StackIT
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── kubernetes.tf
│
├── scripts/                       # Helper Scripts
│   ├── setup-kind.sh              # Create local Kind cluster
│   ├── deploy-local.sh            # Local deployment
│   ├── deploy-gke.sh              # GKE deployment
│   ├── deploy-stackit.sh          # StackIT deployment
│   ├── build-images.sh            # Build Docker images
│   └── cleanup.sh                 # Cleanup script
│
└── .github/                       # CI/CD
    └── workflows/
        ├── build-and-test.yml     # Build & Test Pipeline
        ├── deploy-gcp.yml         # GCP Deployment Pipeline
        └── deploy-stackit.yml     # StackIT Deployment Pipeline
```

---

## Folder Descriptions

### /docs
Contains complete scientific documentation written parallel to development.

### /services
Source code of all microservices. Each service is standalone with its own Dockerfile and tests.

### /kubernetes
All Kubernetes YAML manifests. Separated by environment (local/gke/stackit).

### /terraform
Infrastructure as Code for automatic provisioning of cloud resources.

### /scripts
Shell scripts for recurring tasks (setup, deployment, cleanup).

### /.github/workflows
GitHub Actions CI/CD pipelines for automated testing and deployment.

---

**Date:** 04.02.2025  
**Updated:** On structural changes
