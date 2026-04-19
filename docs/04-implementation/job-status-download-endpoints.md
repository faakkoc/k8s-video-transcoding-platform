# Job Status & Download Endpoints - Implementation

**Datum:** 19.04.2026  
**Status:** ✅ Erfolgreich implementiert und getestet

---

## Übersicht

Mit diesem Feature ist die lokale Plattform vollständig. Nach dem Upload und Transcoding können Jobs jetzt abgefragt und fertige Videos heruntergeladen werden.

### Was wurde implementiert

**Neue Komponenten:**
- `app/routers/jobs.py` — zwei neue Endpoints
- `app/utils/k8s_client.py` — erweitert um `get_job_status()` und `_parse_job_status()`
- `app/main.py` — neuer Router eingebunden

**Neuer Workflow:**
```
Upload → Job läuft → GET /jobs/{job_id} → Status abfragen
                                        ↓
                          GET /download/{job_id} → Presigned URL → Video herunterladen
```

---

## Architektur-Entscheidung: Kein Datenbanken für lokales Deployment

Der ursprüngliche Plan sah PostgreSQL für Job-Metadaten vor. Für das lokale Deployment wurde bewusst darauf verzichtet.

**Begründung:**

Kubernetes speichert die Job-Metadaten bereits vollständig im Job-Objekt selbst. Bei der Job-Erstellung in `create_transcoding_job()` werden `INPUT_KEY`, `OUTPUT_KEY` und `PRESET` als ENV-Variablen in den Container geschrieben:

```python
client.V1EnvVar(name="INPUT_KEY", value=input_key),
client.V1EnvVar(name="OUTPUT_KEY", value=output_key),
client.V1EnvVar(name="PRESET", value=preset),
```

Diese Werte sind über die Kubernetes API jederzeit auslesbar solange der Job existiert (TTL: 24h). Der Kubernetes Job dient damit als temporärer Metadata-Store — eine pragmatische Lösung für das lokale Proof-of-Concept.

**Limitation:** Nach Ablauf der TTL (24h) sind die Metadaten nicht mehr verfügbar. Für das GCP-Deployment wird PostgreSQL (Cloud SQL) eingeführt, das persistente Job-Metadaten über die TTL hinaus speichert.

---

## Implementierung

### 1. k8s_client.py — neue Funktionen

**`get_job_status(job_id)`**

Liest den Kubernetes Job über die API und gibt Status und Metadaten zurück:

```python
def get_job_status(job_id: str) -> dict:
    job = k8s_client.read_namespaced_job(name=job_id, namespace=namespace)

    # Status aus K8s Job Counters ableiten
    status = _parse_job_status(job.status)

    # Metadaten aus Container ENV vars lesen
    env_vars = job.spec.template.spec.containers[0].env
    env_map = {e.name: e.value for e in env_vars}

    return {
        "job_id": job_id,
        "status": status,
        "input_key": env_map.get("INPUT_KEY"),
        "output_key": env_map.get("OUTPUT_KEY"),
        "preset": env_map.get("PRESET"),
        "start_time": job.status.start_time,
        "completion_time": job.status.completion_time,
    }
```

**`_parse_job_status(job_status)`**

Kubernetes speichert keinen einfachen Status-String, sondern Zähler:

| active | succeeded | failed | Unser Status |
|--------|-----------|--------|--------------|
| 0 | 0 | 0 | `pending` |
| 1 | 0 | 0 | `running` |
| 0 | 1 | 0 | `completed` |
| 0 | 0 | 1 | `failed` |

---

### 2. jobs.py — die zwei Endpoints

**`GET /api/v1/jobs/{job_id}`**

Gibt Status und Metadaten eines Jobs zurück. Fehlerbehandlung:
- Job nicht gefunden → HTTP 404
- K8s API nicht erreichbar → HTTP 500

**`GET /api/v1/download/{job_id}`**

Generiert eine Presigned URL für das transcodierte Video. Fehlerbehandlung:
- Job nicht gefunden → HTTP 404
- Job noch nicht abgeschlossen → HTTP 409 (Conflict)
- URL-Generierung fehlgeschlagen → HTTP 500

Presigned URLs sind zeitlich begrenzt (1 Stunde) und enthalten alle nötigen Credentials in der URL selbst — der Client braucht keinen direkten MinIO-Zugang.

---

## Test-Ergebnisse

### Laufende Services

```
NAME                                   READY   STATUS      RESTARTS       AGE
api-gateway-754f8c457d-cgtnq           1/1     Running     0              66m
api-gateway-754f8c457d-hldsm           1/1     Running     0              65m
minio-5d9fdb6985-6p98q                 1/1     Running     3 (103m ago)   6d14h
transcode-20260419-142115-720p-zkcmd   0/1     Completed   0              7m49s
```

### Test 1: Job Status abfragen

```bash
curl http://localhost:8080/api/v1/jobs/transcode-20260419-142115-720p
```

**Response:**
```json
{
  "job_id": "transcode-20260419-142115-720p",
  "status": "completed",
  "preset": "720p",
  "input_key": "1776608474_test-video.mp4",
  "output_key": "1776608474_test-video_720p.mp4",
  "start_time": "2026-04-19T14:21:15Z",
  "completion_time": "2026-04-19T14:21:21Z"
}
```

Job-Dauer: **6 Sekunden** (5-Sekunden Testvideo, 720p Preset).

---

### Test 2: Download URL generieren

```bash
curl http://localhost:8080/api/v1/download/transcode-20260419-142115-720p
```

**Response:**
```json
{
  "job_id": "transcode-20260419-142115-720p",
  "output_key": "1776608474_test-video_720p.mp4",
  "download_url": "http://minio:9000/outputs/1776608474_test-video_720p.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260419%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260419T142345Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=4c7fc90b59867b83bb9b2d5e716a71fbf1fb2e942026e270bce949e3bebb2f53",
  "expires_in_seconds": 3600
}
```

**Hinweis zur URL:** `minio:9000` ist die cluster-interne Adresse. Für den Download von außen wird Port-Forward benötigt (`kubectl port-forward svc/minio 9000:9000`) und `minio:9000` durch `localhost:9000` ersetzt. Im GCP-Deployment wird die URL direkt auf Google Cloud Storage zeigen und öffentlich erreichbar sein.

---

## Vollständiger lokaler API-Stand

| Method | Endpoint | Status | Beschreibung |
|--------|----------|--------|--------------|
| GET | `/` | ✅ | API Info |
| GET | `/api/v1/health` | ✅ | Liveness Probe |
| GET | `/api/v1/ready` | ✅ | Readiness Probe |
| POST | `/api/v1/upload` | ✅ | Video hochladen, Job erstellen |
| GET | `/api/v1/jobs/{job_id}` | ✅ | Job Status abfragen |
| GET | `/api/v1/download/{job_id}` | ✅ | Presigned Download URL |

Die lokale Plattform ist damit funktional vollständig.

---

## Nächste Schritte

### GCP Deployment

Die Infrastruktur wird vor dem Deployment gemeinsam geplant. Kernpunkte:

- **GKE Autopilot** für Kubernetes
- **Google Artifact Registry** für Docker Images
- **Google Cloud Storage** als S3-kompatibler Ersatz für MinIO
- **Cloud SQL (PostgreSQL)** für persistente Job-Metadaten
- **Workload Identity** statt hardcoded Credentials
- **GitHub Actions** für CI/CD

---

**Erstellt:** 19.04.2026  
**Branch:** main  
**Status:** Lokales Deployment vollständig abgeschlossen