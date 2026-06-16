# Projektstruktur

> **Hinweis:** Diese Datei dokumentiert den **aktuellen Ist-Zustand** des Projekts.
> Ursprünglich geplante, aber bewusst nicht implementierte Komponenten (Frontend,
> separater Job-Controller, PostgreSQL) werden in der schriftlichen Ausarbeitung
> als begründete Scoping-Entscheidungen behandelt — nicht als "nicht geschafft".
>
> **StackIT-Deployment ist vollständig implementiert und E2E getestet** (siehe
> `docs/05-deployment/stackit-deployment.md`) — nicht mehr "Future Work".

```
k8s-video-transcoding-platform/
│
├── .gitignore
├── LICENSE                        # Apache 2.0 License
├── README.md                      # Project overview, Quick Start, Cloud-Vergleich
├── STRUCTURE.md                   # Diese Datei
├── kind-config.yaml               # Kind Cluster Konfiguration (lokal)
├── kind-config-registry.yaml      # Kind Cluster + lokale Registry (für Worker-Images)
│
├── docs/                          # Wissenschaftliche Dokumentation
│   ├── README.md                  # Dokumentationsmethode & Struktur
│   │
│   ├── 01-kubernetes-fundamentals/
│   │   ├── container-orchestration.md   # Motivation: Warum K8s für Media-Workflows
│   │   ├── kubernetes-architecture.md   # Control Plane, Worker Nodes, GKE Autopilot
│   │   ├── core-concepts.md             # Pod, Deployment, Job, Service, ConfigMap, RBAC
│   │   └── hands-on-basics.md           # Praktische Grundlagen
│   │
│   ├── 02-microservices-architecture/
│   │   ├── monolith-vs-microservices.md # Vergleich, Warum Microservices für Transcoding
│   │   ├── service-patterns.md          # API Gateway, Strategy Pattern (StorageClient)
│   │   └── media-workflows.md           # Transcoding-Pipeline, Jobs vs. Alternativen
│   │
│   ├── 03-design-decisions/
│   │   ├── storage-strategy.md          # emptyDir → MinIO → Cloud Storage
│   │   ├── storage-abstraction.md       # StorageClient: GCSClient vs. S3Client
│   │   ├── metadata-persistence.md      # K8s Job ENV vs. PostgreSQL (1h TTL)
│   │   ├── transcoding-technology.md    # FFmpeg vs. Cloud Transcoding APIs
│   │   └── kubernetes-patterns.md       # Jobs vs. Deployments, RBAC, TTL
│   │
│   ├── 04-implementation/
│   │   ├── api-gateway-implementation.md
│   │   ├── transcoding-worker-implementation.md
│   │   ├── kubernetes-job-creation.md       # Dynamische V1Job-Erstellung
│   │   ├── upload-feature.md
│   │   ├── job-status-download-endpoints.md
│   │   ├── deployment-success.md
│   │   └── end-to-end-test.md               # Lokaler E2E-Test (Kind + MinIO)
│   │
│   ├── 05-deployment/
│   │   ├── gke-terraform.md             # GKE Autopilot, Workload Identity, IAM
│   │   ├── gke-kubernetes-manifests.md  # K8s Manifests für GKE
│   │   ├── gke-deployment.md            # GKE Deployment-Anleitung
│   │   ├── gke-e2e-test.md              # E2E-Test auf GKE (inkl. Signed URLs)
│   │   ├── cicd-pipelines.md            # GitHub Actions + WIF
│   │   └── stackit-deployment.md        # StackIT (SKE) Deployment — vollständig ✅
│   │
│   └── 06-lessons-learned/
│       ├── challenges.md                # Allgemeine Challenges (lokal/GKE)
│       ├── gke-challenges.md            # GKE-spezifisch, inkl. Signed-URL-Fix
│       ├── cicd-challenges.md           # CI/CD & Workload Identity Federation
│       └── what-worked-well.md          # Positive Erkenntnisse
│
├── services/                      # Microservices Source Code
│   │
│   ├── api-gateway/                # FastAPI Gateway
│   │   ├── app/
│   │   │   ├── main.py             # FastAPI App, Router-Registrierung, CORS
│   │   │   ├── config.py           # Pydantic Settings (ENV-basiert)
│   │   │   ├── routers/
│   │   │   │   ├── health.py       # /health (Liveness), /ready (Readiness)
│   │   │   │   ├── upload.py       # POST /upload
│   │   │   │   └── jobs.py         # GET /jobs/{id}, GET /download/{id}
│   │   │   ├── models/
│   │   │   │   └── job.py          # Pydantic Models (Request/Response)
│   │   │   └── utils/
│   │   │       ├── k8s_client.py       # Dynamische K8s Job-Erstellung & Status
│   │   │       ├── storage_client.py   # StorageClient-Abstraktion: GCSClient + S3Client
│   │   │       └── validators.py       # Datei-Validierung, Settings-basierte Limits
│   │   ├── tests/                  # (aktuell leer)
│   │   ├── .env.example
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── README.md
│   │
│   └── transcoding-worker/         # FFmpeg Transcoding Worker
│       ├── worker.py               # Download → FFmpeg → Upload (GCS/S3-Backend)
│       ├── ffmpeg_presets.py       # 480p/720p/1080p/4k Presets
│       ├── Dockerfile              # jrottenberg/ffmpeg + ENTRYPOINT [] Fix
│       ├── requirements.txt
│       └── README.md
│
├── kubernetes/                     # Kubernetes Manifests
│   │
│   ├── local/                      # Kind (lokale Entwicklung, MinIO)
│   │   ├── 00-namespace.yaml
│   │   └── api-gateway/
│   │       ├── deployment.yaml     # STORAGE_PROVIDER=s3 (MinIO)
│   │       ├── service.yaml
│   │       ├── service-account.yaml
│   │       └── hpa.yaml
│   │
│   ├── gke/                         # GKE Production
│   │   ├── 00-namespace.yaml
│   │   ├── 01-configmap.yaml        # storage_provider: "gcs"
│   │   ├── 02-service-accounts.yaml # Workload Identity Annotations
│   │   └── api-gateway/
│   │       ├── deployment.yaml      # Kein Secret nötig (Workload Identity)
│   │       ├── service.yaml         # LoadBalancer
│   │       └── hpa.yaml             # CPU 70% / Memory 80%, 2-10 Replicas
│   │
│   └── stackit/                     # StackIT Production (SKE) ✅
│       ├── 00-namespace.yaml
│       ├── 01-configmap.yaml        # storage_provider: "s3", S3-Endpoint eu01
│       ├── 02-service-accounts.yaml # Kein Workload Identity — Kommentar erklärt warum
│       └── api-gateway/
│           ├── deployment.yaml      # + imagePullSecrets, S3-Credentials aus Secret
│           ├── service.yaml         # LoadBalancer
│           └── hpa.yaml             # identisch zu GKE
│
├── terraform/                       # Infrastructure as Code
│   │
│   ├── gcp/                         # Google Cloud Platform
│   │   ├── versions.tf              # Provider-Versionen, GCS Backend
│   │   ├── providers.tf
│   │   ├── variables.tf
│   │   ├── terraform.auto.tfvars    # project_id, region (us-east1), etc.
│   │   ├── apis.tf                  # Aktivierte GCP APIs
│   │   ├── gke.tf                   # GKE Autopilot Cluster (Modul)
│   │   ├── storage.tf               # GCS Buckets (uploads/outputs)
│   │   ├── artifact-registry.tf     # Docker Registry (prevent_destroy)
│   │   ├── iam.tf                   # Service Accounts + Workload Identity Bindings
│   │   ├── github-wif.tf            # Workload Identity Federation für CI/CD
│   │   └── outputs.tf
│   │
│   └── stackit/                     # StackIT ✅
│       ├── versions.tf              # Provider-Version, S3-Backend (StackIT Object Storage)
│       ├── providers.tf             # Auth via STACKIT_SERVICE_ACCOUNT_KEY_PATH
│       ├── variables.tf
│       ├── terraform.auto.tfvars    # project_id, region (eu01), cluster_name (v-tc)
│       ├── ske.tf                   # SKE Cluster (Node Pool g1a.2d)
│       ├── storage.tf               # Object Storage Buckets + Credentials
│       └── outputs.tf
│
├── scripts/
│   └── setup-kind.sh                # Erstellt lokalen Kind-Cluster
│
└── .github/                         # CI/CD
    └── workflows/
        ├── build-and-test.yml       # Lint + Docker Build (jeder Push)
        └── deploy-gcp.yml            # Build & Push + Terraform Plan/Apply (WIF)
```

---

## Folder Descriptions

### /docs
Wissenschaftliche Dokumentation, parallel zur Entwicklung geschrieben. Dient als
Grundlage für die schriftliche Ausarbeitung (separates Dokument, nicht Teil
dieses Repos).

### /services
Zwei implementierte Microservices: API Gateway (FastAPI) und Transcoding Worker
(FFmpeg + Python). Ursprünglich geplante Services (Frontend, separater
Job-Controller) wurden bewusst nicht implementiert — die Job-Orchestrierung ist
direkt im API Gateway integriert (`utils/k8s_client.py`), ein Frontend ist durch
die Swagger UI ersetzt.

### /kubernetes
Kubernetes YAML Manifests, getrennt nach Umgebung:
- **local/** — Kind + MinIO (S3-kompatibel)
- **gke/** — GKE Autopilot, Workload Identity (kein Storage-Secret nötig)
- **stackit/** — StackIT SKE, S3-Credentials via Kubernetes Secret + Harbor `imagePullSecret`

Die Manifeste sind strukturell identisch — die Cloud-Agnostik zeigt sich primär
in der ConfigMap (`storage_provider: gcs` vs. `s3`) und den ServiceAccount-Annotations.

### /terraform
Infrastructure as Code für **beide** Cloud-Plattformen:
- **gcp/** — GKE Autopilot, Artifact Registry, Workload Identity (App + CI/CD via WIF)
- **stackit/** — SKE Cluster, Object Storage Buckets + Credentials

StackIT-CI/CD (analog zu `github-wif.tf`) ist als Future Work dokumentiert —
StackIT bietet keine Workload Identity Federation, ein Service Account Key als
GitHub Secret wäre der einzige Weg.

### /.github/workflows
Zwei GitHub Actions Pipelines für GCP: Build & Test (automatisch) und Deploy to
GCP (Apply manuell via `workflow_dispatch`). Für StackIT existiert aktuell keine
Pipeline — Deployment erfolgt manuell (siehe `docs/05-deployment/stackit-deployment.md`).

---

## Bewusste Scoping-Entscheidungen (Future Work)

| Komponente | Status | Begründung |
|------------|--------|------------|
| Frontend | Nicht implementiert | Swagger UI deckt Demo-Zweck ab |
| Separater Job-Controller | Nicht implementiert | Direkt im API Gateway integriert |
| PostgreSQL für Job-Metadaten | Nicht implementiert | K8s Job ENV-Vars ausreichend für PoC (siehe `metadata-persistence.md`) |
| StackIT CI/CD | Nicht implementiert | Kein WIF-Äquivalent auf StackIT; manueller Workflow dokumentiert |

---

**Datum:** 04.02.2025
**Aktualisiert:** 11.06.2026 — StackIT als abgeschlossen markiert, Struktur an Ist-Zustand angepasst
**Status:** Aktueller Ist-Zustand