# GKE Kubernetes Manifests

**Datum:** 21.04.2026
**Aktualisiert:** 27.05.2026 — Workload Identity, us-east1, HMAC Keys entfernt
**Status:** ✅ Vollständig deployed

---

## Übersicht

Die Kubernetes Manifests für das GKE Deployment liegen unter `kubernetes/gke/`. Der entscheidende Unterschied zur lokalen Kind-Konfiguration: Statt MinIO-Endpoints und S3-Credentials wird `STORAGE_PROVIDER=gcs` gesetzt — der Pod authentifiziert sich automatisch via Workload Identity, kein Secret erforderlich.

```
kubernetes/gke/
├── 00-namespace.yaml
├── 01-configmap.yaml
├── 02-service-accounts.yaml
└── api-gateway/
    ├── deployment.yaml
    ├── service.yaml
    └── hpa.yaml
```

---

## Namespace (`00-namespace.yaml`)

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: video-transcoding
```

Der Namespace wird in der CI/CD Pipeline vor `terraform apply` erstellt:

```yaml
- name: Create Namespace
  run: kubectl apply -f kubernetes/gke/00-namespace.yaml
```

---

## ConfigMap (`01-configmap.yaml`)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: platform-config
  namespace: video-transcoding
data:
  # Google Cloud Storage Buckets (von Terraform erstellt)
  input_bucket:  "k8s-transcoding-uploads"
  output_bucket: "k8s-transcoding-outputs"

  # Storage Provider: gcs → GCSClient via Workload Identity (kein Secret!)
  storage_provider: "gcs"

  # Kubernetes
  k8s_namespace: "video-transcoding"

  # Worker Image aus Artifact Registry (us-east1)
  worker_image: "us-east1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/transcoding-worker:latest"
```

**`storage_provider: "gcs"`** ist der entscheidende Unterschied zur lokalen ConfigMap (`storage_provider: "s3"`). Er steuert welche `StorageClient`-Implementierung geladen wird.

**Kein S3-Endpoint, keine Credentials** — GCSClient authentifiziert sich automatisch über den Pod-ServiceAccount via Workload Identity.

---

## Service Accounts & RBAC (`02-service-accounts.yaml`)

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-gateway
  namespace: video-transcoding
  annotations:
    # Workload Identity: verknüpft K8s ServiceAccount mit GCP ServiceAccount
    iam.gke.io/gcp-service-account: api-gateway@k8s-transcoding-plattform.iam.gserviceaccount.com
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: transcoding-worker
  namespace: video-transcoding
  annotations:
    iam.gke.io/gcp-service-account: transcoding-worker@k8s-transcoding-plattform.iam.gserviceaccount.com
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: api-gateway-role
  namespace: video-transcoding
rules:
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["create", "get", "list", "watch", "delete"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
```

Die `iam.gke.io/gcp-service-account` Annotation ist der Schlüssel für Workload Identity: GKE injiziert automatisch ein Token das dem Pod erlaubt, als der verknüpfte GCP ServiceAccount zu agieren — ohne Credentials im Cluster.

---

## API Gateway Deployment (`api-gateway/deployment.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: video-transcoding
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-gateway
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    spec:
      serviceAccountName: api-gateway
      containers:
        - name: api-gateway
          image: us-east1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/api-gateway:latest
          imagePullPolicy: Always
          env:
            # Storage Provider → steuert GCSClient vs S3Client
            - name: STORAGE_PROVIDER
              valueFrom:
                configMapKeyRef:
                  name: platform-config
                  key: storage_provider

            # Kein S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY mehr!
            # GCSClient nutzt Workload Identity automatisch

            - name: IMAGE_PULL_POLICY
              value: "Always"
            - name: TRANSCODING_WORKER_IMAGE
              valueFrom:
                configMapKeyRef:
                  name: platform-config
                  key: worker_image
            - name: INPUT_BUCKET
              valueFrom:
                configMapKeyRef:
                  name: platform-config
                  key: input_bucket
            - name: OUTPUT_BUCKET
              valueFrom:
                configMapKeyRef:
                  name: platform-config
                  key: output_bucket
            - name: K8S_NAMESPACE
              valueFrom:
                configMapKeyRef:
                  name: platform-config
                  key: k8s_namespace
```

**Vergleich lokal vs. GKE:**

| | Lokal (Kind) | GKE |
|--|--|--|
| `STORAGE_PROVIDER` | `s3` | `gcs` |
| `S3_ENDPOINT` | `http://minio:9000` | — (nicht gesetzt) |
| `S3_ACCESS_KEY` | `minioadmin` | — (nicht gesetzt) |
| Authentifizierung | Hardcoded Credentials | Workload Identity |
| Secret im Cluster | Nein | Nein |

**`imagePullPolicy: Always`:** GKE muss bei jedem Pod-Start das Image aus der Artifact Registry prüfen — im Gegensatz zu lokal (`IfNotPresent`).

---

## Service (`api-gateway/service.yaml`)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
  namespace: video-transcoding
spec:
  type: LoadBalancer
  selector:
    app: api-gateway
  ports:
    - name: http
      port: 80
      targetPort: http
```

**`type: LoadBalancer`:** GKE erstellt automatisch einen Google Cloud Load Balancer mit einer externen IP. Die IP wird bei jedem Cluster-Neustart neu vergeben.

Zugewiesene Public IP: **`<EXTERNAL-IP>`**

---

## Worker Job Template (dynamisch in k8s_client.py)

Der Transcoding Worker wird nicht als statisches Manifest deployed — `k8s_client.py` erstellt den Job dynamisch. Für GKE übergibt der API Gateway `STORAGE_PROVIDER=gcs` an den Worker-Job:

```python
env_vars = [
    client.V1EnvVar(name="STORAGE_PROVIDER", value=storage_provider),  # "gcs"
    client.V1EnvVar(name="INPUT_BUCKET",     value=os.getenv("INPUT_BUCKET")),
    client.V1EnvVar(name="OUTPUT_BUCKET",    value=os.getenv("OUTPUT_BUCKET")),
    # S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY nur bei provider == "s3"
]
```

Der Worker-Pod nutzt denselben `transcoding-worker` ServiceAccount mit Workload Identity Annotation — er kann auf GCS zugreifen ohne Credentials.

---

## Horizontal Pod Autoscaler (`api-gateway/hpa.yaml`)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  scaleTargetRef:
    kind: Deployment
    name: api-gateway
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

---

**Nächstes Dokument:** [Step-by-Step Deployment & E2E Test](./gke-e2e-test.md)