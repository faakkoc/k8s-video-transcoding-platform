# GKE Deployment: Übersicht

**Datum:** 21.04.2026
**Status:** ✅ Erfolgreich — End-to-End Test bestanden

---

## Übersicht

Dieses Kapitel dokumentiert das Deployment der Video Transcoding Platform auf Google Kubernetes Engine (GKE). Nach dem erfolgreichen lokalen Deployment auf Kind wird die Plattform in einer echten Cloud-Umgebung betrieben.

Das GKE Deployment demonstriert zwei zentrale Aspekte des Projekts:

- **Cloud-Agnostik:** Derselbe Anwendungscode läuft ohne Änderungen in der Cloud — lediglich Konfiguration (ENV-Variablen, ConfigMaps, Secrets) wird angepasst.
- **Infrastructure as Code:** Die gesamte GCP-Infrastruktur wird über Terraform provisioniert und ist reproduzierbar.

---

## Zielarchitektur

```
Internet
    │
    ▼
┌─────────────────────────────────────────────────────┐
│              GKE Autopilot Cluster                  │
│              (us-central1, GCP)                     │
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
               │ boto3 S3-API (HMAC Keys)
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
| **Object Storage** | MinIO | Google Cloud Storage (GCS) |
| **Credentials** | Hardcoded (minioadmin) | HMAC Keys (Kubernetes Secret) |
| **Ingress** | Port-Forward | LoadBalancer Service (Public IP) |
| **Infrastruktur** | Manuell | Terraform |

---

## Wichtige Design-Entscheidung: HMAC Keys statt Workload Identity

Für den GCS-Zugriff wurden HMAC Keys anstelle von Workload Identity verwendet.

**Begründung:** boto3 nutzt das AWS SigV4-Protokoll für die S3-kompatible API. GCS unterstützt zwar die S3-kompatible API, aber Workload Identity (GCP-natives Auth-Verfahren) ist mit boto3 nicht kompatibel — boto3 erwartet Access Key + Secret Key.

HMAC Keys ermöglichen es, dieselbe boto3-Abstraktion für GCS und StackIT Object Storage zu verwenden. Der Code bleibt cloud-agnostisch.

```
Workload Identity → funktioniert nur mit google-cloud-storage (nicht boto3)
HMAC Keys        → funktioniert mit boto3 → identischer Code für GCS + StackIT ✅
```

Die HMAC Keys werden von Terraform erstellt und als Kubernetes Secret im Cluster abgelegt.

---

## Deployment-Übersicht (Schritte)

Das GKE Deployment besteht aus vier Phasen:

1. **Terraform** — GCP Infrastruktur provisionieren
2. **Docker** — Images bauen und in Artifact Registry pushen
3. **Kubernetes** — Manifests anwenden
4. **Test** — End-to-End Test

Details zu jedem Schritt in den folgenden Dokumenten:

- [Terraform Infrastruktur](./gke-terraform.md)
- [Kubernetes Manifests](./gke-kubernetes-manifests.md)
- [Step-by-Step Deployment & E2E Test](./gke-e2e-test.md)

---

## Ergebnis

| Komponente | Status |
|------------|--------|
| GKE Autopilot Cluster | ✅ Running |
| API Gateway (2 Replicas) | ✅ Running |
| LoadBalancer Public IP | ✅ `<EXTERNAL-IP>` |
| GCS Buckets (uploads/outputs) | ✅ Erstellt |
| Artifact Registry | ✅ Images gepusht |
| HMAC Credentials | ✅ Kubernetes Secret |
| Upload Endpoint | ✅ HTTP 201 |
| Transcoding Job | ✅ Completed |
| GCS Output | ✅ `393.9 KB` |

---

**Nächstes Dokument:** [Terraform Infrastruktur](./gke-terraform.md)