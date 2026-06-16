# Monolith vs. Microservices

**Datum:** 04.02.2025
**Status:** Abgeschlossen

---

## Monolithische Architektur

In einem Monolithen läuft die gesamte Anwendungslogik in einem einzigen Prozess:
Upload-Handling, Transcoding-Logik, Job-Verwaltung, Storage-Zugriff — alles
zusammen deployed und skaliert.

```
┌──────────────────────────────────────────┐
│              Monolith                    │
│                                          │
│  Upload-Handler                          │
│  Transcoding-Engine (FFmpeg)             │
│  Job-Queue                               │
│  Storage-Client                          │
│  REST API                                │
└──────────────────────────────────────────┘
         │
         ▼
    Skalierung: gesamter Monolith × N
```

**Problem für Video-Transcoding:** Transcoding ist CPU-intensiv und dauert
lange. In einem Monolithen würde ein Upload-Request den Server für Minuten
blockieren — alle anderen Requests müssten warten.

---

## Microservices-Architektur

Einzelne, klar abgegrenzte Services mit je einer Verantwortlichkeit:

```
┌──────────────┐     ┌───────────────────────────────┐
│  API Gateway │────▶│    Kubernetes Job              │
│  (FastAPI)   │     │    (Transcoding Worker)        │
│              │     │    → FFmpeg                    │
│  - Upload    │     └───────────────────────────────┘
│  - Status    │
│  - Download  │     ┌───────────────────────────────┐
└──────────────┘     │    Object Storage              │
                     │    (GCS / StackIT / MinIO)     │
                     └───────────────────────────────┘
```

Jeder Service ist unabhängig skalierbar, deploybar und wartbar.

---

## Vergleich

| Kriterium | Monolith | Microservices |
|-----------|----------|---------------|
| **Skalierung** | Alles oder nichts | Gezielt (nur Worker) |
| **Deployment** | Alles zusammen | Unabhängig pro Service |
| **Fehlertoleranz** | Ein Fehler = Totalausfall | Isoliert pro Service |
| **Komplexität** | Niedrig (ein Prozess) | Höher (Netzwerk, Orchestrierung) |
| **Technologie** | Eine Sprache/Runtime | Flexibel pro Service |
| **Geeignet für** | Einfache Anwendungen | Komplexe, skalierbare Systeme |

---

## Warum Microservices für Video-Transcoding?

**Unabhängige Skalierung:** Bei hoher Last werden nur Transcoding-Worker
skaliert — nicht der API Gateway. Der API Gateway läuft dauerhaft mit 2
Replicas, Worker entstehen on-demand als Kubernetes Jobs.

**Isolation:** Ein fehlgeschlagener Transcoding-Job beeinflusst den API
Gateway nicht. Der Retry-Mechanismus (`backoff_limit: 3`) läuft im Job,
nicht im API Gateway.

**Ressourcen-Trennung:** Der API Gateway braucht wenig RAM (256Mi requests).
Ein Transcoding-Worker braucht deutlich mehr (512Mi requests, 2Gi limit für
FFmpeg). Separate Services erlauben separate Resource-Profiles.

---

## Bewusste Vereinfachungen in diesem Projekt

Klassische Microservices-Architekturen nutzen Message Queues (RabbitMQ, Kafka)
für asynchrone Kommunikation zwischen Services. In diesem Projekt wurde das
bewusst vereinfacht:

- **Kein Message Broker** — der API Gateway erstellt K8s Jobs direkt via
  Kubernetes API. Einfacher, aber weniger entkoppelt.
- **Kein separater Job-Controller** — Job-Erstellung und Status-Abfrage sind
  direkt im API Gateway integriert (`utils/k8s_client.py`).
- **Kein Frontend-Service** — Swagger UI ersetzt das React-Frontend für Demo-Zwecke.

Diese Vereinfachungen sind als bewusste Scoping-Entscheidungen dokumentiert,
nicht als technische Limitationen. Kubernetes übernimmt die Queue-Funktion
implizit: Jobs warten im `Pending`-Status bis Ressourcen verfügbar sind.