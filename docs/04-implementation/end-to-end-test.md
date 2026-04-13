# End-to-End Test - Video Transcoding Platform

**Datum:** 13.04.2026  
**Status:** ✅ Erfolgreich

---

## Übersicht

Dieser Bericht dokumentiert den ersten erfolgreichen End-to-End-Test der Video Transcoding Platform auf dem lokalen Kind-Cluster. Der Test beweist, dass der gesamte Workflow — vom Video-Upload bis zum fertig transcodierten Output in MinIO — vollständig funktioniert.

---

## Testumgebung

| Komponente | Version / Details |
|------------|-------------------|
| **OS** | CachyOS (Arch Linux) |
| **Docker** | 27.x |
| **Kind** | v0.31.0 |
| **kubectl** | v1.35.0 |
| **Kubernetes** | v1.32 (via Kind) |
| **Helm** | v4.1.3 |
| **Cluster** | `video-transcoding` (1 control-plane, 2 worker nodes) |
| **Namespace** | `video-transcoding` |

---

## Laufende Services vor dem Test

```bash
kubectl get pods -n video-transcoding

NAME                              READY   STATUS    RESTARTS      AGE
api-gateway-fd6489fc7-bmttx       1/1     Running   0             4m22s
api-gateway-fd6489fc7-drn68       1/1     Running   0             4m34s
minio-5d9fdb6985-6p98q            1/1     Running   1 (35m ago)   20h
```

**MinIO Buckets (vor Test):**

```
Name       Objects   Size    Access
outputs    0         0.0 B   R/W
uploads    0         0.0 B   R/W
```

---

## Getesteter Workflow

```
1. Test-Video erstellen (FFmpeg testsrc)
       ↓
2. Upload via Swagger UI (POST /api/v1/upload)
       ↓
3. API Gateway: Datei validieren → zu MinIO hochladen (uploads bucket)
       ↓
4. API Gateway: Kubernetes Job erstellen (transcode-20260413-201024-720p)
       ↓
5. Worker Pod startet (transcoding-worker:latest)
       ↓
6. Worker: Download Input von MinIO (uploads bucket)
       ↓
7. Worker: FFmpeg Transcoding (720p Preset)
       ↓
8. Worker: Upload Output zu MinIO (outputs bucket)
       ↓
9. Job: Complete 1/1 ✅
```

---

## Schritt-für-Schritt Protokoll

### Schritt 1: Test-Video erstellen

```bash
ffmpeg -f lavfi -i testsrc=duration=5:size=1280x720:rate=30 \
       -c:v libx264 -pix_fmt yuv420p /tmp/test-video.mp4
```

Erzeugt eine synthetische 5-Sekunden-Testdatei (1280x720, H.264).

---

### Schritt 2: Upload via Swagger UI

Aufgerufen über `http://localhost:8080/api/v1/docs`:

- **Endpoint:** `POST /api/v1/upload`
- **File:** `test-video.mp4`
- **Preset:** `720p`

**Response (HTTP 201):**

```json
{
  "job_id": "transcode-20260413-201024-720p",
  "status": "pending",
  "input_filename": "test-video.mp4",
  "preset": "720p",
  "created_at": "2026-04-13T20:10:24Z"
}
```

---

### Schritt 3: Job und Pod beobachten

```bash
watch kubectl get jobs,pods -n video-transcoding
```

**Ergebnis:**

```
NAME                                       STATUS     COMPLETIONS   DURATION   AGE
job.batch/transcode-20260413-201024-720p   Complete   1/1           6s         43s

NAME                                       READY   STATUS      RESTARTS   AGE
pod/api-gateway-fd6489fc7-bmttx            1/1     Running     0          4m22s
pod/api-gateway-fd6489fc7-drn68            1/1     Running     0          4m34s
pod/minio-5d9fdb6985-6p98q                 1/1     Running     1          20h
pod/transcode-20260413-201024-720p-7mhjh   0/1     Completed   0          43s
```

Der Job benötigte **6 Sekunden** für ein 5-Sekunden-Testvideo mit 720p Preset.

---

### Schritt 4: Ergebnis in MinIO

**MinIO Buckets (nach Test):**

```
Name       Objects   Size       Access
uploads    1         73.1 KiB   R/W
outputs    1         345.5 KiB  R/W
```

---

## Worker Logs

```bash
kubectl logs -n video-transcoding transcode-20260413-201024-720p-7mhjh
```

```
[INIT] Transcoding Worker
   Job ID: transcode-20260413-201024-720p
   Preset: 720p
   S3 Endpoint: http://minio:9000
   Input: s3://uploads/1776111023_test-video.mp4
   Output: s3://outputs/1776111023_test-video_720p.mp4
============================================================
TRANSCODING JOB: transcode-20260413-201024-720p
============================================================
[START] Downloading input from MinIO...
[OK] Downloaded 0.07 MB
[START] Starting FFmpeg transcoding...
   Command: ffmpeg -i /tmp/1776111023_test-video.mp4 -y -c:v libx264 -b:v 2500k -vf scale=1280x720 -r 30 -preset medium -profile:v high -c:a aac -b:a 128k -movflags +faststart /tmp/1776111023_test-video_720p.mp4
[OK] Transcoding completed in 2.3 seconds
[START] Uploading output to MinIO...
[OK] Uploaded 0.34 MB to s3://outputs/1776111023_test-video_720p.mp4
[CLEANUP] Removing temporary files...
   Deleted: /tmp/1776111023_test-video.mp4
   Deleted: /tmp/1776111023_test-video_720p.mp4
============================================================
JOB COMPLETED SUCCESSFULLY: transcode-20260413-201024-720p
============================================================
```

---

## Kubernetes Job Details

```bash
kubectl describe job transcode-20260413-201024-720p -n video-transcoding
```

```
Name:                        transcode-20260413-201024-720p
Namespace:                   video-transcoding
Selector:                    batch.kubernetes.io/controller-uid=05457993-f47d-4a90-9134-9ceffc20de0b
Labels:                      app=transcoding-worker
                             job-type=video-transcode
                             preset=720p
Annotations:                 <none>
Parallelism:                 1
Completions:                 1
Completion Mode:             NonIndexed
Suspend:                     false
Backoff Limit:               3
TTL Seconds After Finished:  86400
Start Time:                  Mon, 13 Apr 2026 22:10:24 +0200
Completed At:                Mon, 13 Apr 2026 22:10:30 +0200
Duration:                    6s
Pods Statuses:               0 Active (0 Ready) / 1 Succeeded / 0 Failed
Pod Template:
  Labels:  app=transcoding-worker
           batch.kubernetes.io/controller-uid=05457993-f47d-4a90-9134-9ceffc20de0b
           batch.kubernetes.io/job-name=transcode-20260413-201024-720p
           controller-uid=05457993-f47d-4a90-9134-9ceffc20de0b
           job-id=transcode-20260413-201024-720p
           job-name=transcode-20260413-201024-720p
  Containers:
   transcoder:
    Image:      transcoding-worker:latest
    Port:       <none>
    Host Port:  <none>
    Limits:
      cpu:     2
      memory:  2Gi
    Requests:
      cpu:     500m
      memory:  512Mi
    Environment:
      S3_ENDPOINT:    http://minio:9000
      S3_ACCESS_KEY:  minioadmin
      S3_SECRET_KEY:  minioadmin123
      INPUT_BUCKET:   uploads
      OUTPUT_BUCKET:  outputs
      INPUT_KEY:      1776111023_test-video.mp4
      OUTPUT_KEY:     1776111023_test-video_720p.mp4
      PRESET:         720p
      JOB_ID:         transcode-20260413-201024-720p
    Mounts:           <none>
  Volumes:            <none>
  Node-Selectors:     <none>
  Tolerations:        <none>
Events:
  Type    Reason            Age   From            Message
  ----    ------            ----  ----            -------
  Normal  SuccessfulCreate  17m   job-controller  Created pod: transcode-20260413-201024-720p-7mhjh
  Normal  Completed         17m   job-controller  Job completed
```

---

## Wichtigste Technische Erkenntnisse

### 1. ENTRYPOINT-Fix (kritisch)

Das Base-Image `jrottenberg/ffmpeg:4.4-ubuntu` setzt `ENTRYPOINT ["ffmpeg"]`. Ohne explizites Überschreiben würde `CMD ["python", "worker.py"]` als FFmpeg-Argument interpretiert:

```
ffmpeg python worker.py  → crash
```

**Fix im Dockerfile:**

```dockerfile
ENTRYPOINT []
CMD ["python", "worker.py"]
```

Ohne diesen Fix würde kein Worker-Job jemals erfolgreich starten.

---

### 2. Image-Loading via `kind load`

Statt einer lokalen Registry wird `kind load docker-image` verwendet. Der anfangs getestete Registry-Ansatz (`localhost:5001`) hat unnötige Komplexität ohne Mehrwert für lokale Entwicklung eingeführt.

```bash
kind load docker-image transcoding-worker:latest --name video-transcoding
kind load docker-image api-gateway:latest --name video-transcoding
```

Alle Deployments und Jobs nutzen `imagePullPolicy: IfNotPresent`.

---

### 3. MinIO als S3-kompatibler Storage

MinIO übernimmt die Rolle von AWS S3 / Google Cloud Storage in der lokalen Umgebung. Die boto3-Schnittstelle ist identisch — für das Cloud-Deployment werden lediglich Endpoint-URL und Credentials ausgetauscht.

```python
# Lokal:
S3_ENDPOINT = "http://minio:9000"

# GCP Production (identischer Code!):
S3_ENDPOINT = "https://storage.googleapis.com"
```

Das bestätigt das Cloud-Agnostik-Design der Architektur.

---

## Vollständiger lokaler Deployment-Stand

| Komponente | Status | Details |
|------------|--------|---------|
| **Kind Cluster** | ✅ | 1 control-plane, 2 worker nodes |
| **Namespace** | ✅ | `video-transcoding` |
| **API Gateway** | ✅ | 2 Replicas, Running |
| **MinIO** | ✅ | Helm-Deploy, Buckets `uploads`/`outputs` |
| **RBAC** | ✅ | ServiceAccount kann Jobs erstellen |
| **HPA** | ✅ | 2-10 Replicas, CPU/Memory-basiert |
| **Transcoding Worker** | ✅ | Image geladen, Jobs laufen durch |
| **S3 Integration** | ✅ | Upload → MinIO → Worker → MinIO |

---

## Noch nicht implementiert

| Feature | Priorität | Geschätzter Aufwand |
|---------|-----------|---------------------|
| `GET /api/v1/jobs/{job_id}` | Hoch | ~30 Min |
| `GET /api/v1/jobs` | Mittel | ~20 Min |
| `GET /api/v1/download/{job_id}` | Hoch | ~45 Min |
| React Frontend | Niedrig | Optional (Swagger UI reicht) |

---

## Nächste Schritte

### Phase 1: Lokale Plattform abschließen

1. Job-Status-Endpoint implementieren (`GET /api/v1/jobs/{job_id}`)
2. Download-Endpoint mit Presigned URL implementieren (`GET /api/v1/download/{job_id}`)
3. End-to-End-Demo mit vollständigem Download-Flow durchführen

### Phase 2: GCP Deployment

1. Terraform für GKE Autopilot + GCS Buckets + Artifact Registry
2. GitHub Actions CI/CD Pipeline
3. Workload Identity statt hardcoded Credentials
4. Deployment mit gleichen Kubernetes-Manifests (nur ConfigMaps anpassen)

### Phase 3: StackIT Deployment

1. Terraform für SKE + StackIT Object Storage
2. Gleiche Manifests, anderer Cloud-Provider
3. Beweist Cloud-Agnostik der Architektur

---

**Erstellt:** 13.04.2026  
**Branch:** fix/transcoding-worker  
**Nächstes Update:** Nach Job-Status und Download-Endpoint Implementation