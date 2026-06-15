# Dokumentation

Diese Dokumentation begleitet die Entwicklung der Video Transcoding Platform
und dient als Grundlage für die wissenschaftliche Ausarbeitung.

## Struktur

### 01 - Kubernetes Fundamentals
Grundlagen der Container-Orchestrierung mit Kubernetes:
- Motivation: Warum K8s für Media-Workflows?
- Pods, Deployments, Services, Jobs

### 03 - Design Decisions
Technologie-Auswahl und begründete Trade-offs:
- Storage-Strategie (emptyDir → MinIO → Cloud)
- StorageClient-Abstraktion (GCSClient vs. S3Client)
- Metadata-Persistenz (K8s Job ENV vs. PostgreSQL)
- Transcoding-Technologie (FFmpeg vs. Cloud-APIs)
- Kubernetes-Patterns (Jobs vs. Deployments, RBAC, TTL)

> **Hinweis:** `02-microservices-architecture/` wurde nicht implementiert —
> die relevanten Architektur-Entscheidungen sind in `03-design-decisions/` dokumentiert.

### 04 - Implementation
Schrittweise Implementierung mit Challenges und Lösungen:
- API Gateway, Transcoding Worker, Kubernetes Job-Erstellung
- Upload, Status, Download Endpoints
- Lokaler E2E-Test (Kind + MinIO)

### 05 - Deployment
Production Deployments auf beiden Cloud-Plattformen:
- GKE (Terraform, Workload Identity, CI/CD)
- StackIT (SKE, Harbor, S3-Credentials) ✅
- CI/CD Pipelines (GitHub Actions + WIF)

### 06 - Lessons Learned
Erkenntnisse, Challenges und Evaluation:
- GKE-spezifische Challenges (inkl. Signed URL Fix)
- CI/CD Challenges (Workload Identity Federation)
- Was gut funktioniert hat

---

## Dokumentationsmethode

Diese Dokumentation wurde **parallel zur Entwicklung** erstellt:

1. **Vor der Implementierung** — Planung, Architektur-Entscheidungen
2. **Während der Implementierung** — Code-Snippets, Challenges, Lösungen
3. **Nach der Implementierung** — Evaluation, Lessons Learned

---

**Begonnen:** Februar 2025
**Abgeschlossen:** Juni 2026