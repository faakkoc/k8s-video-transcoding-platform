# GKE Deployment: Step-by-Step & End-to-End Test

**Datum:** 21.04.2026
**Aktualisiert:** 16.06.2026 — Workload Identity, us-east1, CI/CD-Pipeline, Download-Endpoint
**Status:** ✅ Erfolgreich

---

## Voraussetzungen

| Tool | Version |
|------|---------|
| gcloud CLI | aktuell |
| terraform | v1.14.x |
| docker | 27.x |
| kubectl | v1.35.x |
| Fish Shell | (lokale Entwicklungsumgebung) |

Authentifizierung:

```fish
gcloud auth login
gcloud auth application-default login
gcloud config set project k8s-transcoding-plattform
```

Docker für Artifact Registry konfigurieren:

```fish
gcloud auth configure-docker us-east1-docker.pkg.dev
```

---

## Phase 1: Terraform Apply

```fish
cd terraform/gcp
terraform init    # Remote Backend initialisieren, Provider laden
terraform plan    # Änderungen prüfen
terraform apply   # Infrastruktur erstellen
```

`terraform apply` provisioniert folgende Ressourcen:
- GCP APIs aktivieren
- GKE Autopilot Cluster (us-east1)
- GCS Buckets (uploads + outputs)
- Artifact Registry (`us-east1-docker.pkg.dev`)
- Service Accounts (`api-gateway`, `transcoding-worker`)
- Workload Identity Bindings (inkl. `roles/iam.serviceAccountTokenCreator` für Signed URLs)
- Workload Identity Federation für GitHub Actions CI/CD

**Dauer:** ca. 10–15 Minuten (GKE Autopilot Cluster-Erstellung dauert am längsten)

> **Hinweis:** Es gibt kein manuell verwaltetes Kubernetes Secret für Storage-Credentials —
> Authentication läuft vollständig über Workload Identity. Der Pod-ServiceAccount
> wird automatisch mit dem GCP-ServiceAccount verknüpft.

---

## Phase 2: Credentials holen & Manifests anwenden

Nach jedem `terraform apply` müssen die GKE Credentials neu geholt werden:

```fish
gcloud container clusters get-credentials video-transcoding \
  --region us-east1 \
  --project k8s-transcoding-plattform
```

Manifests anwenden:

```fish
kubectl apply -f kubernetes/gke/00-namespace.yaml
kubectl apply -f kubernetes/gke/01-configmap.yaml
kubectl apply -f kubernetes/gke/02-service-accounts.yaml
kubectl apply -f kubernetes/gke/api-gateway/
```

Prüfen:

```fish
kubectl get pods -n video-transcoding
# NAME                           READY   STATUS    RESTARTS   AGE
# api-gateway-7f7d974bbb-2f6v8   1/1     Running   0          56s
# api-gateway-7f7d974bbb-mvrvk   1/1     Running   0          2m53s
```

---

## Phase 3: Docker Images (CI/CD oder manuell)

**Via CI/CD Pipeline (Normalfall):**

Jeder Push auf `main` triggert automatisch Build & Push zur Artifact Registry.
`terraform apply` erfolgt manuell via `Actions → Deploy to GCP → Run workflow → apply=true`.

**Manuell (nach frischem terraform apply):**

```fish
# API Gateway
docker build -t us-east1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/api-gateway:latest \
  services/api-gateway/
docker push us-east1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/api-gateway:latest

# Transcoding Worker
docker build -t us-east1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/transcoding-worker:latest \
  services/transcoding-worker/
docker push us-east1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/transcoding-worker:latest
```

Danach Rollout:

```fish
kubectl rollout restart deployment/api-gateway -n video-transcoding
kubectl rollout status deployment/api-gateway -n video-transcoding
# deployment "api-gateway" successfully rolled out
```

Public IP ermitteln:

```fish
kubectl get svc -n video-transcoding
# NAME          TYPE           CLUSTER-IP    EXTERNAL-IP      PORT(S)
# api-gateway   LoadBalancer   10.x.x.x      <EXTERNAL-IP>   80:xxxxx/TCP
```

---

## Phase 4: End-to-End Test

### Schritt 1: Video hochladen

Über Swagger UI (`http://<EXTERNAL-IP>/api/v1/docs`) oder curl:

```fish
curl -X POST http://<EXTERNAL-IP>/api/v1/upload \
  -F "file=@/tmp/test-video.mp4" \
  -F "preset=720p"
```

**Response (HTTP 201):**

```json
{
  "job_id": "transcode-1781044594-a1b2c3-720p",
  "status": "pending",
  "input_filename": "test-video.mp4",
  "preset": "720p",
  "created_at": "2026-06-09T22:29:54.000Z",
  "message": "Job created successfully. File uploaded to storage."
}
```

### Schritt 2: Job und Pod beobachten

```fish
kubectl get pods -n video-transcoding -w

# NAME                                         READY   STATUS              AGE
# api-gateway-7f7d974bbb-2f6v8                 1/1     Running             5m
# api-gateway-7f7d974bbb-mvrvk                 1/1     Running             7m
# transcode-1781044594-a1b2c3-720p-vqkt8       0/1     Pending             0s
# transcode-1781044594-a1b2c3-720p-vqkt8       0/1     Pending             50s  ← Autopilot fährt Node hoch
# transcode-1781044594-a1b2c3-720p-vqkt8       0/1     ContainerCreating   60s
# transcode-1781044594-a1b2c3-720p-vqkt8       1/1     Running             94s
# transcode-1781044594-a1b2c3-720p-vqkt8       0/1     Completed           3m30s
```

Der Pod ist zunächst `Pending` weil GKE Autopilot einen neuen Node hochfahren muss — ca. 60–90 Sekunden Cold-Start-Latenz.

### Schritt 3: Worker Logs

```fish
kubectl logs -n video-transcoding transcode-1781044594-a1b2c3-720p-vqkt8
```

```
[INIT] Storage: GCS (Workload Identity)
[INIT] Transcoding Worker
   Job ID: transcode-1781044594-a1b2c3-720p
   Preset: 720p
   Input: k8s-transcoding-uploads/1781044438_test-video.mp4
   Output: k8s-transcoding-outputs/1781044438_test-video_720p.mp4
============================================================
TRANSCODING JOB: transcode-1781044594-a1b2c3-720p
============================================================
[START] Downloading input...
[OK] Downloaded 0.07 MB
[START] Starting FFmpeg transcoding...
   Command: ffmpeg -i /tmp/1781044438_test-video.mp4 -y -c:v libx264 -b:v 2500k
            -vf scale=1280x720 -r 30 -preset medium -profile:v high
            -c:a aac -b:a 128k -movflags +faststart
            /tmp/1781044438_test-video_720p.mp4
[OK] Transcoding completed in 8.9 seconds
[START] Uploading output...
[OK] Uploaded 0.38 MB to k8s-transcoding-outputs/1781044438_test-video_720p.mp4
[CLEANUP] Removing temporary files...
============================================================
JOB COMPLETED SUCCESSFULLY: transcode-1781044594-a1b2c3-720p
============================================================
```

### Schritt 4: Job Status abfragen

```fish
curl http://<EXTERNAL-IP>/api/v1/jobs/transcode-1781044594-a1b2c3-720p
```

```json
{
  "job_id": "transcode-1781044594-a1b2c3-720p",
  "status": "completed",
  "preset": "720p",
  "input_key": "1781044438_test-video.mp4",
  "output_key": "1781044438_test-video_720p.mp4",
  "start_time": "2026-06-09T22:29:54Z",
  "completion_time": "2026-06-09T22:30:23Z"
}
```

### Schritt 5: Download URL generieren

```fish
curl http://<EXTERNAL-IP>/api/v1/download/transcode-1781044594-a1b2c3-720p
```

```json
{
  "job_id": "transcode-1781044594-a1b2c3-720p",
  "output_key": "1781044438_test-video_720p.mp4",
  "download_url": "https://storage.googleapis.com/k8s-transcoding-outputs/...?X-Goog-Signature=...",
  "expires_in_seconds": 3600
}
```

Die Signed URL wird via IAM Credentials API generiert (Workload Identity kompatibel,
kein Private Key nötig) — sie ist 1 Stunde gültig.

---

## Ergebnis

| Schritt | Ergebnis |
|---------|----------|
| Upload (POST /upload) | ✅ HTTP 201, Job erstellt |
| GCS Upload (Input) | ✅ `k8s-transcoding-uploads` |
| Kubernetes Job | ✅ Erstellt, Completed |
| GKE Autopilot Scale-Up | ✅ Neuer Node in ~90s |
| FFmpeg Transcoding | ✅ 8.9 Sekunden |
| GCS Upload (Output) | ✅ 380 KB in `k8s-transcoding-outputs` |
| Job Status API | ✅ `status: completed` |
| Download URL (Signed URL) | ✅ HTTP 200, GCS Signed URL |

---

## Infrastruktur abbauen

```fish
cd terraform/gcp
terraform destroy -target=module.gke \
  -target=google_service_account_iam_member.api_gateway_workload_identity \
  -target=google_service_account_iam_member.worker_workload_identity
```

Artifact Registry, GCS Buckets und WIF-Ressourcen haben `prevent_destroy = true`
und bleiben erhalten — nur der GKE Cluster wird abgebaut.

---

**Nächstes Dokument:** [GKE Challenges & Lessons Learned](../06-lessons-learned/gke-challenges.md)