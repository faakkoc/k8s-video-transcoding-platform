# GKE Deployment: Step-by-Step & End-to-End Test

**Datum:** 21.04.2026
**Status:** ✅ Erfolgreich

---

## Voraussetzungen

| Tool | Version |
|------|---------|
| gcloud CLI | aktuell |
| terraform | v1.14.8 |
| docker | 27.x |
| kubectl | v1.35.0 |
| Fish Shell | (lokale Entwicklungsumgebung) |

Authentifizierung:

```fish
gcloud auth login
gcloud auth application-default login
gcloud config set project k8s-transcoding-plattform
```

Docker für Artifact Registry konfigurieren:

```fish
gcloud auth configure-docker us-central1-docker.pkg.dev
```

---

## Phase 1: Namespace erstellen (vor Terraform!)

Der Kubernetes Namespace muss **vor** `terraform apply` existieren, da Terraform das HMAC-Secret direkt über die K8s API anlegt. Dafür wird zuerst die GKE Cluster-Verbindung hergestellt:

```fish
# GKE Credentials holen
gcloud container clusters get-credentials video-transcoding \
  --region us-central1 \
  --project k8s-transcoding-plattform

# Namespace anlegen
kubectl apply -f kubernetes/gke/00-namespace.yaml
```

---

## Phase 2: Terraform Apply

```fish
cd terraform/gcp
terraform init    # Remote Backend initialisieren, Provider laden
terraform plan    # Änderungen prüfen
terraform apply   # Infrastruktur erstellen
```

`terraform apply` provisioniert 24 Ressourcen:
- GCP APIs aktivieren
- GKE Autopilot Cluster
- GCS Buckets (uploads + outputs)
- Artifact Registry
- Service Accounts + IAM Bindings
- HMAC Keys
- Kubernetes Secret `gcs-hmac-credentials`

**Dauer:** ca. 10–15 Minuten (GKE Autopilot Cluster-Erstellung dauert am längsten)

---

## Phase 3: Kubernetes Manifests anwenden

```fish
kubectl apply -f kubernetes/gke/01-configmap.yaml
kubectl apply -f kubernetes/gke/02-service-accounts.yaml
kubectl apply -f kubernetes/gke/api-gateway/
```

Secret prüfen (sollte von Terraform bereits erstellt sein):

```fish
kubectl get secrets -n video-transcoding
# NAME                   TYPE     DATA   AGE
# gcs-hmac-credentials   Opaque   4      5m
```

---

## Phase 4: Docker Images bauen und pushen

Nach jedem `terraform apply` oder Code-Änderung müssen die Images neu gebaut und gepusht werden, da `terraform destroy` die Artifact Registry inklusive Images löscht:

```fish
# API Gateway
docker build -t us-central1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/api-gateway:latest \
  services/api-gateway/
docker push us-central1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/api-gateway:latest

# Transcoding Worker
docker build -t us-central1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/transcoding-worker:latest \
  services/transcoding-worker/
docker push us-central1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/transcoding-worker:latest
```

---

## Phase 5: Deployment starten und prüfen

```fish
kubectl rollout restart deployment/api-gateway -n video-transcoding
kubectl rollout status deployment/api-gateway -n video-transcoding
# deployment "api-gateway" successfully rolled out

kubectl get pods -n video-transcoding
# NAME                           READY   STATUS    RESTARTS   AGE
# api-gateway-7f7d974bbb-2f6v8   1/1     Running   0          56s
# api-gateway-7f7d974bbb-mvrvk   1/1     Running   0          2m53s
```

Public IP des LoadBalancers ermitteln:

```fish
kubectl get svc -n video-transcoding
# NAME          TYPE           CLUSTER-IP    EXTERNAL-IP      PORT(S)
# api-gateway   LoadBalancer   10.x.x.x      <EXTERNAL-IP>   80:xxxxx/TCP
```

Health Check:

```fish
curl http://<EXTERNAL-IP>/api/v1/health
# {"status": "healthy", "service": "Video Transcoding API Gateway"}
```

---

## Phase 6: End-to-End Test

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
  "job_id": "transcode-20260421-191719-720p",
  "status": "pending",
  "input_filename": "test-video.mp4",
  "preset": "720p",
  "created_at": "2026-04-21T19:17:19.000Z"
}
```

### Schritt 2: Job und Pod beobachten

```fish
kubectl get pods -n video-transcoding -w

# NAME                                   READY   STATUS              AGE
# api-gateway-7f7d974bbb-2f6v8           1/1     Running             5m
# api-gateway-7f7d974bbb-mvrvk           1/1     Running             7m
# transcode-20260421-191719-720p-vqkt8   0/1     Pending             0s
# transcode-20260421-191719-720p-vqkt8   0/1     Pending             50s  ← GKE Autopilot fährt Node hoch
# transcode-20260421-191719-720p-vqkt8   0/1     Pending             60s
# transcode-20260421-191719-720p-vqkt8   0/1     ContainerCreating   60s
# transcode-20260421-191719-720p-vqkt8   1/1     Running             94s
# transcode-20260421-191719-720p-vqkt8   0/1     Completed           3m30s
```

Der Pod ist zunächst `Pending` weil GKE Autopilot einen neuen Node hochfahren muss — das dauert ca. 60–90 Sekunden.

### Schritt 3: Worker Logs

```fish
kubectl logs -n video-transcoding transcode-20260421-191719-720p-vqkt8 --follow
```

```
[INIT] Transcoding Worker
   Job ID: transcode-20260421-191719-720p
   Preset: 720p
   S3 Endpoint: https://storage.googleapis.com
   Input: s3://k8s-transcoding-uploads/1776799037_test-video.mp4
   Output: s3://k8s-transcoding-outputs/1776799037_test-video_720p.mp4
============================================================
TRANSCODING JOB: transcode-20260421-191719-720p
============================================================
[START] Downloading input from GCS...
[OK] Downloaded 0.07 MB
[START] Starting FFmpeg transcoding...
   Command: ffmpeg -i /tmp/1776799037_test-video.mp4 -y -c:v libx264 -b:v 2500k
            -vf scale=1280x720 -r 30 -preset medium -profile:v high
            -c:a aac -b:a 128k -movflags +faststart
            /tmp/1776799037_test-video_720p.mp4
[OK] Transcoding completed in 8.9 seconds
[START] Uploading output to GCS...
[OK] Uploaded 0.38 MB to s3://k8s-transcoding-outputs/1776799037_test-video_720p.mp4
[CLEANUP] Removing temporary files...
   Deleted: /tmp/1776799037_test-video.mp4
   Deleted: /tmp/1776799037_test-video_720p.mp4
============================================================
JOB COMPLETED SUCCESSFULLY: transcode-20260421-191719-720p
============================================================
```

### Schritt 4: Output in GCS prüfen

In der GCP Console unter `k8s-transcoding-outputs`:

```
Name                                    Size
1776799037_test-video_720p.mp4         393.9 KB
```

### Schritt 5: Job Status abfragen

```fish
curl http://<EXTERNAL-IP>/api/v1/jobs/transcode-20260421-191719-720p
```

```json
{
  "job_id": "transcode-20260421-191719-720p",
  "status": "completed",
  "preset": "720p",
  "input_key": "1776799037_test-video.mp4",
  "output_key": "1776799037_test-video_720p.mp4",
  "start_time": "2026-04-21T19:17:19Z",
  "completion_time": "2026-04-21T19:20:49Z"
}
```

---

## Ergebnis

| Schritt | Ergebnis |
|---------|----------|
| Upload (POST /upload) | ✅ HTTP 201, Job erstellt |
| GCS Upload (Input) | ✅ `k8s-transcoding-uploads` |
| Kubernetes Job | ✅ Created, Completed |
| GKE Autopilot Scale-Up | ✅ Neuer Node in ~90s |
| FFmpeg Transcoding | ✅ 8.9 Sekunden |
| GCS Upload (Output) | ✅ 393.9 KB in `k8s-transcoding-outputs` |
| Job Status API | ✅ `status: completed` |

---

## Infrastruktur abbauen

Nach dem Test kann die gesamte Infrastruktur mit einem Befehl abgebaut werden:

```fish
cd terraform/gcp
terraform destroy
```

`terraform destroy` löscht alle 24 Ressourcen inklusive GKE Cluster, GCS Buckets und Artifact Registry. Der Remote State-Bucket (`k8s-transcoding-tfstate`) wird nicht gelöscht — er muss manuell entfernt werden, falls nicht mehr benötigt.

**Hinweis:** Nach einem `terraform destroy` und erneutem `terraform apply` müssen die Docker Images neu gebaut und gepusht werden, da die Artifact Registry gelöscht wurde. Eine CI/CD Pipeline würde diesen Schritt automatisieren.

---

**Nächstes Dokument:** [GKE Challenges & Lessons Learned](../06-lessons-learned/gke-challenges.md)