# GKE Deployment: Übersicht

**Datum:** 21.04.2026
**Aktualisiert:** 27.05.2026 — Storage-Abstraktion auf Workload Identity umgestellt
**Status:** ✅ Erfolgreich — End-to-End Test bestanden

---

## Übersicht

Dieses Kapitel dokumentiert das Deployment der Video Transcoding Platform auf Google Kubernetes Engine (GKE). Nach dem erfolgreichen lokalen Deployment auf Kind wird die Plattform in einer echten Cloud-Umgebung betrieben.

Das GKE Deployment demonstriert zwei zentrale Aspekte des Projekts:

- **Cloud-Agnostik:** Derselbe Anwendungscode läuft ohne Änderungen in der Cloud — lediglich Konfiguration (ENV-Variablen, ConfigMaps) wird angepasst.
- **Infrastructure as Code:** Die gesamte GCP-Infrastruktur wird über Terraform provisioniert und ist reproduzierbar.

---

## Zielarchitektur

```
Internet
    │
    ▼
┌─────────────────────────────────────────────────────┐
│              GKE Autopilot Cluster                  │
│              (us-east1, GCP)                        │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │         Namespace: video-transcoding         │   │
│  │                                             │   │
│  │  ┌──────────────────┐                       │   │
│  │  │   API Gateway    │ ← LoadBalancer        │   │
│  │  │  (2 Replicas)    │   Public IP           │   │
│  │  └────────┬─────────┘                       │   │
│  │           │ create K8s Job                  │   │
│  │           ▼                                 │   │
│  │  ┌──────────────────┐                       │   │
│  │  │ Transcoding Job  │ (on demand)           │   │
│  │  │  Worker Pod      │                       │   │
│  │  └────────┬─────────┘                       │   │
│  │           │                                 │   │
│  └───────────┼─────────────────────────────────┘   │
└──────────────┼──────────────────────────────────────┘
               │ google-cloud-storage (Workload Identity)
               ▼
┌──────────────────────────────────┐
│     Google Cloud Storage         │
│  ┌──────────────┐ ┌───────────┐  │
│  │   uploads    │ │  outputs  │  │
│  │   bucket     │ │  bucket   │  │
│  └──────────────┘ └───────────┘  │
└──────────────────────────────────┘
```

---

## Technologie-Stack (GKE)

| Komponente | Lokal (Kind) | GKE |
|------------|--------------|-----|
| **Kubernetes** | Kind v0.31.0 | GKE Autopilot |
| **Container Registry** | `kind load` | Google Artifact Registry |
| **Object Storage** | MinIO (S3-kompatibel) | Google Cloud Storage |
| **Storage Auth** | Hardcoded (minioadmin) | Workload Identity (kein Secret) |
| **Storage Client** | boto3 (S3Client) | google-cloud-storage (GCSClient) |
| **Ingress** | Port-Forward | LoadBalancer Service (Public IP) |
| **Infrastruktur** | Manuell | Terraform |
| **CI/CD** | — | GitHub Actions + WIF |

---

## Wichtige Design-Entscheidung: Storage-Abstraktion mit Workload Identity

### Warum nicht boto3 für GCS?

Der initiale Ansatz nutzte HMAC Keys um boto3 mit der S3-kompatiblen GCS-API zu verwenden. Das hatte Nachteile:

- HMAC Keys müssen manuell rotiert werden
- Kubernetes Secret im Cluster erforderlich
- Credentials-Management zusätzliche Komplexität

### Lösung: StorageClient-Abstraktion

Eine abstrakte `StorageClient`-Klasse mit zwei Implementierungen:

```python
# Gesteuert über STORAGE_PROVIDER ENV-Variable
def get_storage_client() -> StorageClient:
    provider = os.getenv("STORAGE_PROVIDER", "s3")
    if provider == "gcs":
        return GCSClient()   # google-cloud-storage + Workload Identity
    return S3Client()        # boto3 für MinIO/StackIT
```

**`GCSClient`** — für GKE:
- Nutzt `google-cloud-storage` Library
- Authentifizierung automatisch via GKE Workload Identity
- **Kein Secret im Cluster notwendig**
- Pod-ServiceAccount → GCP ServiceAccount → GCS Bucket

**`S3Client`** — für lokal und StackIT:
- Nutzt `boto3` mit S3-kompatibler API
- Credentials via ENV-Variablen (`S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`)

```
GKE:    STORAGE_PROVIDER=gcs → GCSClient → Workload Identity → GCS ✅
Lokal:  STORAGE_PROVIDER=s3  → S3Client  → MinIO              ✅
StackIT: STORAGE_PROVIDER=s3 → S3Client  → StackIT S3         ✅
```

Der Anwendungscode bleibt identisch — nur die ConfigMap ändert sich pro Umgebung.

---

## Deployment-Übersicht (Schritte)

Das GKE Deployment besteht aus vier Phasen:

1. **Terraform** — GCP Infrastruktur provisionieren
2. **CI/CD** — Images bauen und in Artifact Registry pushen (automatisch via GitHub Actions)
3. **Kubernetes** — Manifests anwenden (via Pipeline)
4. **Test** — End-to-End Test

Details zu jedem Schritt in den folgenden Dokumenten:

- [Terraform Infrastruktur](./gke-terraform.md)
- [Kubernetes Manifests](./gke-kubernetes-manifests.md)
- [Step-by-Step Deployment & E2E Test](./gke-e2e-test.md)
- [CI/CD Pipelines](./cicd-pipelines.md)

---

## Ergebnis

| Komponente | Status |
|------------|--------|
| GKE Autopilot Cluster (us-east1) | ✅ Running |
| API Gateway (2 Replicas) | ✅ Running |
| LoadBalancer Public IP | ✅ `<EXTERNAL-IP>` |
| GCS Buckets (uploads/outputs) | ✅ Erstellt |
| Artifact Registry | ✅ Images gepusht via CI/CD |
| Workload Identity | ✅ Kein Secret erforderlich |
| Upload Endpoint | ✅ HTTP 201 |
| Transcoding Job | ✅ Completed |
| GCS Output | ✅ 393.9 KB |

---

**Nächstes Dokument:** [Terraform Infrastruktur](./gke-terraform.md)