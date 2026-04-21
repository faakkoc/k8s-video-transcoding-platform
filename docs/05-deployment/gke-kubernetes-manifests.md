# GKE Kubernetes Manifests

**Datum:** 21.04.2026
**Status:** ✅ Vollständig deployed

---

## Übersicht

Die Kubernetes Manifests für das GKE Deployment liegen unter `kubernetes/gke/` und sind analog zur lokalen Kind-Konfiguration aufgebaut. Der entscheidende Unterschied: Statt lokaler MinIO-Endpoints und hardcoded Credentials werden die Werte aus ConfigMaps und Secrets gelesen, die auf GCS und die HMAC Keys zeigen.

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

**Wichtig:** Der Namespace muss **vor** `terraform apply` erstellt werden, da Terraform das HMAC-Secret direkt über die Kubernetes API anlegt und der Namespace dafür existieren muss.

```fish
kubectl apply -f kubernetes/gke/00-namespace.yaml
# erst danach: terraform apply
```

---

## ConfigMap (`01-configmap.yaml`)

Die ConfigMap enthält alle nicht-sensitiven Konfigurationswerte:

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

  # GCS S3-kompatibler Endpoint
  s3_endpoint: "https://storage.googleapis.com"

  # GCS erfordert "auto" statt einer AWS-Region
  s3_region: "auto"

  # Kubernetes
  k8s_namespace: "video-transcoding"

  # Worker Image aus Artifact Registry
  worker_image: "us-central1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/transcoding-worker:latest"
```

**`s3_region: "auto"`:** GCS S3-kompatible API erfordert `auto` als Region-Wert statt einer konkreten AWS-Region wie `us-east-1`. boto3 leitet daraus die korrekte Signatur-Region ab.

**`worker_image`:** Der vollständige Artifact Registry Pfad des Transcoding Worker Images. Dieser Wert wird vom API Gateway genutzt um Worker-Jobs mit dem korrekten Image zu erstellen.

---

## Service Accounts & RBAC (`02-service-accounts.yaml`)

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-gateway
  namespace: video-transcoding
  annotations:
    # Workload Identity Annotation (für zukünftige google-cloud-storage Migration)
    iam.gke.io/gcp-service-account: api-gateway@k8s-transcoding-plattform.iam.gserviceaccount.com
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
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: api-gateway-rolebinding
  namespace: video-transcoding
subjects:
  - kind: ServiceAccount
    name: api-gateway
roleRef:
  kind: Role
  name: api-gateway-role
  apiGroup: rbac.authorization.k8s.io
```

Die RBAC-Konfiguration ist identisch mit dem lokalen Deployment — der API Gateway darf nur Jobs erstellen und lesen, keine anderen Cluster-Ressourcen manipulieren.

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
    metadata:
      labels:
        app: api-gateway
    spec:
      serviceAccountName: api-gateway
      containers:
        - name: api-gateway
          image: us-central1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/api-gateway:latest
          imagePullPolicy: Always
          ports:
            - name: http
              containerPort: 8000
          env:
            # Image Pull Policy für Worker-Jobs
            - name: IMAGE_PULL_POLICY
              value: "Always"

            # Worker Image aus ConfigMap
            - name: TRANSCODING_WORKER_IMAGE
              valueFrom:
                configMapKeyRef:
                  name: platform-config
                  key: worker_image

            # GCS Bucket-Konfiguration aus ConfigMap
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
            - name: S3_ENDPOINT
              valueFrom:
                configMapKeyRef:
                  name: platform-config
                  key: s3_endpoint
            - name: S3_REGION
              valueFrom:
                configMapKeyRef:
                  name: platform-config
                  key: s3_region

            # HMAC Credentials aus Secret (für API Gateway)
            - name: S3_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: gcs-hmac-credentials
                  key: api-gateway-access-key
            - name: S3_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: gcs-hmac-credentials
                  key: api-gateway-secret

            # HMAC Credentials für Worker-Jobs (werden weitergegeben)
            - name: WORKER_S3_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: gcs-hmac-credentials
                  key: worker-access-key
            - name: WORKER_S3_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: gcs-hmac-credentials
                  key: worker-secret

            # Kubernetes Namespace
            - name: K8S_NAMESPACE
              valueFrom:
                configMapKeyRef:
                  name: platform-config
                  key: k8s_namespace

          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"

          livenessProbe:
            httpGet:
              path: /api/v1/health
              port: http
            initialDelaySeconds: 10
            periodSeconds: 30
            failureThreshold: 3

          readinessProbe:
            httpGet:
              path: /api/v1/ready
              port: http
            initialDelaySeconds: 5
            periodSeconds: 10
```

**`imagePullPolicy: Always`:** Im Gegensatz zum lokalen Deployment mit `IfNotPresent` muss GKE bei jedem Pod-Start das Image aus der Artifact Registry prüfen. Das stellt sicher, dass nach einem `docker push` auch das neue Image genutzt wird.

**Worker Credentials weitergeben:** Der API Gateway erhält sowohl seine eigenen HMAC Credentials (`S3_ACCESS_KEY`, `S3_SECRET_KEY`) als auch die Worker-Credentials (`WORKER_S3_ACCESS_KEY`, `WORKER_S3_SECRET_KEY`). Bei der Job-Erstellung in `k8s_client.py` werden die Worker-Credentials als ENV-Variablen in den Job-Pod geschrieben.

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
      targetPort: 8000
```

**`type: LoadBalancer`:** Im Gegensatz zum lokalen Deployment (Port-Forward) wird in GKE ein Cloud Load Balancer provisioniert. GKE erstellt automatisch eine externe IP-Adresse.

Zugewiesene Public IP: **`<EXTERNAL-IP>`** (wird bei jedem Cluster-Neustart neu vergeben)

Der API ist erreichbar unter:
- Swagger UI: `http://<EXTERNAL-IP>/api/v1/docs`
- Upload: `POST http://<EXTERNAL-IP>/api/v1/upload`

---

## Horizontal Pod Autoscaler (`api-gateway/hpa.yaml`)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
  namespace: video-transcoding
spec:
  scaleTargetRef:
    apiVersion: apps/v1
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
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

Der HPA skaliert den API Gateway automatisch zwischen 2 und 10 Replicas basierend auf CPU- und Memory-Auslastung. Bei erhöhtem Upload-Traffic werden automatisch weitere Instanzen hochgefahren.

---

## Worker Job Template (dynamisch in k8s_client.py)

Der Transcoding Worker wird nicht als statisches Manifest deployed, sondern dynamisch durch den API Gateway als Kubernetes Job erstellt. Die relevanten Felder im generierten Job:

```python
client.V1Container(
    name="transcoder",
    image=os.getenv("TRANSCODING_WORKER_IMAGE", "transcoding-worker:latest"),
    image_pull_policy=os.getenv("IMAGE_PULL_POLICY", "IfNotPresent"),
    env=[
        # GCS Konfiguration (aus API Gateway ENV weitergegeben)
        client.V1EnvVar(name="S3_ENDPOINT",    value=os.getenv("S3_ENDPOINT")),
        client.V1EnvVar(name="S3_ACCESS_KEY",  value=os.getenv("WORKER_S3_ACCESS_KEY")),
        client.V1EnvVar(name="S3_SECRET_KEY",  value=os.getenv("WORKER_S3_SECRET_KEY")),
        client.V1EnvVar(name="INPUT_BUCKET",   value=os.getenv("INPUT_BUCKET")),
        client.V1EnvVar(name="OUTPUT_BUCKET",  value=os.getenv("OUTPUT_BUCKET")),
        # Job-spezifische Werte
        client.V1EnvVar(name="INPUT_KEY",  value=input_key),
        client.V1EnvVar(name="OUTPUT_KEY", value=output_key),
        client.V1EnvVar(name="PRESET",     value=preset),
        client.V1EnvVar(name="JOB_ID",     value=job_id),
    ],
    resources=client.V1ResourceRequirements(
        requests={"memory": "512Mi", "cpu": "500m"},
        limits={"memory": "2Gi",    "cpu": "2000m"}
    )
)
```

Der API Gateway liest seine eigene ENV-Konfiguration und gibt sie an den Worker-Job weiter. Damit ist sichergestellt, dass Worker-Jobs immer die korrekte GCS-Konfiguration erhalten — unabhängig davon, ob der Cluster lokal oder in der Cloud läuft.

---

**Nächstes Dokument:** [Step-by-Step Deployment & E2E Test](./gke-e2e-test.md)