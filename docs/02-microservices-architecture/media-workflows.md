# Media-Workflows auf Kubernetes

**Datum:** 04.02.2025
**Status:** Abgeschlossen

---

## Anforderungen von Media-Workflows

Video-Transcoding hat spezifische Anforderungen, die klassische Web-Anwendungen
nicht haben:

| Anforderung | Beschreibung | Kubernetes-Lösung |
|-------------|-------------|-------------------|
| **Burst Traffic** | Live-Events → plötzlich viele Uploads | HPA + Autopilot |
| **CPU-Intensität** | 4K-Transcoding benötigt viele CPU-Cores | Resource Limits, dedizierte Worker |
| **Lange Laufzeit** | Jobs dauern Sekunden bis Minuten | Kubernetes Jobs (kein Timeout) |
| **Asynchron** | Upload sofort, Ergebnis später | Job-Status-Polling |
| **Isolation** | Fehler in einem Job betrifft andere nicht | Separate Pods pro Job |

---

## Transcoding-Pipeline in diesem Projekt

```
Client
  │
  │ POST /upload (multipart/form-data)
  ▼
API Gateway (FastAPI)
  │
  ├─ Datei validieren (Format, Größe)
  ├─ Upload zu Object Storage (Input-Bucket)
  │   └─ GCS (GKE) oder StackIT Object Storage
  │
  ├─ Kubernetes Job erstellen
  │   └─ k8s_client.create_transcoding_job()
  │
  └─ job_id zurückgeben (HTTP 201)

Client
  │
  │ GET /jobs/{job_id}   (Polling)
  ▼
API Gateway
  │
  └─ K8s Job Status lesen → "pending" / "running" / "completed" / "failed"

Transcoding Worker (K8s Job)
  │
  ├─ Input-Video von Object Storage herunterladen
  ├─ FFmpeg ausführen (Preset: 480p/720p/1080p/4k)
  ├─ Output-Video zu Object Storage hochladen
  └─ Pod beendet sich → Job: Completed

Client
  │
  │ GET /download/{job_id}
  ▼
API Gateway
  │
  └─ Presigned/Signed URL generieren → Client lädt direkt von Storage herunter
```

---

## Warum Kubernetes Jobs für Transcoding?

Kubernetes Jobs sind die natürliche Lösung für Batch-Workloads:

**Completion-Tracking:** Ein Job ist abgeschlossen wenn ein Pod erfolgreich
endet (Exit Code 0). Das ist semantisch korrekt für Transcoding — "fertig"
bedeutet "erfolgreich transcodiert", nicht "läuft seit X Minuten".

**Automatische Retries:** Bei transientem Fehler (Netzwerk-Timeout beim
Download, kurzzeitige Ressourcen-Knappheit) startet Kubernetes automatisch
einen neuen Pod — bis `backoff_limit` (3 Versuche) erreicht ist.

**Ressourcenfreigabe:** Nach Completion gibt der Pod Ressourcen frei.
`ttl_seconds_after_finished: 3600` löscht den Job-Eintrag nach 1h automatisch
aus etcd — der Cluster bleibt sauber.

**On-Demand-Skalierung:** Auf GKE Autopilot wird für jeden Job ein neuer
Node provisioniert wenn nötig. 10 parallele Jobs = 10 parallele Pods auf
so vielen Nodes wie nötig — vollautomatisch.

---

## Vergleich: Kubernetes Jobs vs. alternative Ansätze

| Ansatz | Vorteile | Nachteile |
|--------|----------|-----------|
| **K8s Jobs** (gewählt) | Built-in Retry, Completion-Tracking, TTL | Cold-Start auf Autopilot |
| **Message Queue (RabbitMQ)** | Entkopplung, Backpressure, Prioritäten | Zusätzliche Infrastruktur |
| **Cloud Transcoding API** (z.B. AWS MediaConvert) | Keine eigene Infrastruktur | Cloud-Lock-in, höhere Kosten |
| **Serverless** (Cloud Functions) | Kein Cold-Start-Problem | Timeout-Limits, weniger Kontrolle |

Für dieses Projekt (PoC, Cloud-Agnostik als Ziel) sind Kubernetes Jobs die
optimale Wahl: kein Cloud-Lock-in, volle Kontrolle über FFmpeg-Konfiguration,
und Kubernetes übernimmt Orchestrierung, Retry und Cleanup.