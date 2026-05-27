# Projektstruktur

> **Hinweis:** Diese Datei dokumentiert den **aktuellen Ist-Zustand** des Projekts.
> Ursprünglich geplante aber nicht implementierte Komponenten (Frontend, Job-Controller)
> werden in der schriftlichen Ausarbeitung als "Future Work" behandelt.

```
k8s-video-transcoding-platform/
│
├── .gitignore
├── LICENSE                        # Apache 2.0 License
├── README.md                      # Project overview
├── STRUCTURE.md                   # Diese Datei
│
├── docs/                          # Scientific documentation
│   ├── README.md
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
│   │   ├── cloud-agnostic-design.md
│   │   ├── storage-strategy.md
│   │   ├── metadata-persistence.md
│   │   ├── transcoding-technology.md
│   │   └── kubernetes-patterns.md
│   │
│   ├── 04-implementation/
│   │   ├── development-setup.md
│   │   ├── api-gateway-implementation.md
│   │   ├── transcoding-worker-implementation.md
│   │   ├── kubernetes-job-creation.md
│   │   ├── upload-feature.md
│   │   ├── job-status-download-endpoints.md
│   │   ├── deployment-success.md
│   │   └── end-to-end-test.md
│   │
│   ├── 05-deployment/
│   │   ├── local-kind.md
│   │   ├── gke-deployment.md
│   │   ├── gke-terraform.md
│   │   ├── gke-kubernetes-manifests.md
│   │   ├── gke-e2e-test.md
│   │   ├── cicd-pipelines.md
│   │   └── stackit-deployment.md  # Future Work
│   │
│   └── 06-lessons-learned/
│       ├── challenges.md
│       ├── what-worked-well.md
│       ├── gke-challenges.md
│       └── cicd-challenges.md
│
├── services/                      # Microservices Source Code
│   │
│   ├── api-gateway/               # FastAPI Gateway
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── routers/
│   │   │   │   ├── health.py
│   │   │   │   ├── upload.py
│   │   │   │   └── jobs.py
│   │   │   ├── models/
│   │   │   │   └── job.py
│   │   │   └── utils/
│   │   │       ├── k8s_client.py
│   │   │       ├── storage_client.py  # GCSClient + S3Client Abstraktion
│   │   │       ├── s3_client.py       # Legacy (lokale Entwicklung)
│   │   │       └── validators.py
│   │   ├── tests/
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
│   │   └── api-gateway/
│   │       ├── deployment.yaml    # MinIO/S3 Konfiguration
│   │       ├── service.yaml
│   │       ├── service-account.yaml
│   │       └── hpa.yaml
│   │
│   └── gke/                       # GKE Production
│       ├── 00-namespace.yaml
│       ├── 01-configmap.yaml      # STORAGE_PROVIDER=gcs
│       ├── 02-service-accounts.yaml
│       └── api-gateway/
│           ├── deployment.yaml    # Workload Identity, kein Secret
│           ├── service.yaml       # LoadBalancer
│           └── hpa.yaml
│
├── terraform/                     # Infrastructure as Code
│   │
│   ├── gcp/                       # Google Cloud Platform
│   │   ├── versions.tf
│   │   ├── providers.tf
│   │   ├── variables.tf
│   │   ├── terraform.auto.tfvars
│   │   ├── apis.tf
│   │   ├── gke.tf
│   │   ├── storage.tf
│   │   ├── artifact-registry.tf
│   │   ├── iam.tf                 # Service Accounts + Workload Identity
│   │   ├── github-wif.tf          # Workload Identity Federation für CI/CD
│   │   └── outputs.tf
│   │
│   └── stackit/                   # Future Work
│
├── scripts/
│   └── setup-kind.sh
│
└── .github/                       # CI/CD
    └── workflows/
        ├── build-and-test.yml     # Lint + Docker Build (jeder Push)
        └── deploy-gcp.yml         # Build & Push + Terraform Plan/Apply
```

---

## Folder Descriptions

### /docs
Wissenschaftliche Dokumentation, parallel zur Entwicklung geschrieben.

### /services
Zwei implementierte Microservices: API Gateway (FastAPI) und Transcoding Worker (FFmpeg + Python).
Ursprünglich geplante Services (Frontend, Job-Controller) wurden bewusst nicht implementiert —
die Job-Orchestrierung ist direkt im API Gateway integriert, ein Frontend ist durch die Swagger UI ersetzt.

### /kubernetes
Kubernetes YAML Manifests getrennt nach Umgebung. GKE nutzt Workload Identity (kein Secret für Storage),
lokal wird MinIO via S3-kompatibler API genutzt.

### /terraform
Infrastructure as Code für GCP. StackIT-Deployment ist als Future Work geplant.

### /.github/workflows
Zwei GitHub Actions Pipelines: Build & Test (automatisch) und Deploy to GCP (Apply manuell via workflow_dispatch).

---

**Datum:** 27.05.2026
**Status:** Aktueller Ist-Zustand