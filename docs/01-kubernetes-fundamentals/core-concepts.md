# Kubernetes Core Concepts

**Datum:** 04.02.2025
**Status:** Abgeschlossen

---

## Übersicht

Kubernetes arbeitet deklarativ: man beschreibt den **gewünschten Zustand**
(z.B. "2 Replicas des API Gateway") und Kubernetes sorgt dafür, dass dieser
Zustand erreicht und aufrechterhalten wird. Die Kernkonzepte sind die
Bausteine aus denen dieser Zustand zusammengesetzt wird.

---

## Pod

Die kleinste deploybare Einheit in Kubernetes. Ein Pod enthält einen oder
mehrere Container, die sich Netzwerk und Storage teilen.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: api-gateway-pod
spec:
  containers:
    - name: api-gateway
      image: us-east1-docker.pkg.dev/.../api-gateway:latest
      ports:
        - containerPort: 8000
```

**Wichtig:** Pods sind ephemeral — sie können jederzeit neu erstellt werden.
Daher werden Pods nie direkt deployed, sondern immer über höhere Abstraktionen
(Deployment, Job).

---

## Deployment

Beschreibt den gewünschten Zustand einer Applikation: wie viele Replicas,
welches Image, welche Resources. Der Deployment Controller sorgt dafür,
dass dieser Zustand immer erreicht wird.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
spec:
  replicas: 2                    # Immer 2 Pods laufend halten
  selector:
    matchLabels:
      app: api-gateway
  template:
    spec:
      containers:
        - name: api-gateway
          image: .../api-gateway:latest
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
```

**Relevanz:** Der API Gateway läuft als Deployment mit 2 Replicas
(`kubernetes/gke/api-gateway/deployment.yaml`).

---

## Job

Für Batch-Workloads die eine Aufgabe ausführen und dann enden. Ein Job
erstellt einen oder mehrere Pods, wartet auf erfolgreichen Abschluss und
markiert sich selbst als `Completed`.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: transcode-1781044594-a1b2c3-720p
spec:
  backoff_limit: 3               # Max 3 Retry-Versuche
  ttl_seconds_after_finished: 3600  # Cleanup nach 1h
  template:
    spec:
      restart_policy: Never
      containers:
        - name: transcoder
          image: .../transcoding-worker:latest
          env:
            - name: PRESET
              value: "720p"
```

**Warum Jobs statt Deployments für Transcoding?**

| Kriterium | Deployment | Job |
|-----------|-----------|-----|
| Lebensdauer | Dauerhaft laufend | Endet nach Completion |
| Completion-Tracking | Nicht vorgesehen | Built-in |
| Retry bei Failure | Immer (restart) | Kontrolliert (backoff_limit) |
| Ressourcenfreigabe | Manuell | Automatisch nach TTL |
| Geeignet für | API Server, Webserver | Transcoding, Batch-Tasks |

---

## Service

Stellt einen stabilen Netzwerk-Endpunkt für eine Gruppe von Pods bereit.
Ohne Service wäre die IP eines Pods unbekannt (sie ändert sich bei jedem Neustart).

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
spec:
  type: LoadBalancer      # Erstellt eine externe IP (GCP/StackIT Load Balancer)
  selector:
    app: api-gateway      # Leitet Traffic an alle Pods mit diesem Label
  ports:
    - port: 80
      targetPort: 8000
```

**Service-Typen:**
- `ClusterIP` — nur intern erreichbar (lokal/Kind)
- `LoadBalancer` — erstellt externe IP via Cloud Provider (GKE, SKE)
- `NodePort` — Port auf jedem Node (selten)

---

## ConfigMap

Speichert Konfigurationsdaten als Key-Value-Paare, getrennt vom Container-Image.
Änderungen an der Konfiguration erfordern keinen Image-Rebuild.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: platform-config
data:
  storage_provider: "gcs"        # "gcs" für GKE, "s3" für StackIT
  input_bucket: "k8s-transcoding-uploads"
  k8s_namespace: "video-transcoding"
```

**Kernidee der Cloud-Agnostik:** Derselbe Code läuft auf GKE und StackIT —
der einzige Unterschied ist `storage_provider: gcs` vs. `storage_provider: s3`
in der jeweiligen ConfigMap.

---

## Secret

Wie ConfigMap, aber für sensitive Daten (Passwörter, Tokens, Keys).
Wird base64-kodiert in etcd gespeichert.

```yaml
# Erstellt via kubectl, nicht als YAML im Repo:
kubectl create secret generic s3-credentials \
  --from-literal=access-key=<key> \
  --from-literal=secret-key=<secret>
```

**Unterschied GKE vs. StackIT:**
- GKE: Kein Storage-Secret nötig — Workload Identity authentifiziert den Pod
  automatisch bei GCS
- StackIT: `s3-credentials` Secret mit Access/Secret Key, da kein Workload
  Identity verfügbar

---

## Namespace

Logische Trennung von Ressourcen innerhalb eines Clusters. Alle Ressourcen
dieses Projekts laufen im Namespace `video-transcoding`.

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: video-transcoding
```

---

## HorizontalPodAutoscaler (HPA)

Skaliert ein Deployment automatisch basierend auf Metriken (CPU, Memory).

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
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

Der API Gateway hat einen HPA auf beiden Cloud-Plattformen
(`kubernetes/gke/api-gateway/hpa.yaml`, `kubernetes/stackit/api-gateway/hpa.yaml`).

---

## ServiceAccount & RBAC

Ein ServiceAccount ist eine Identität für Pods. Über RBAC (Role-Based Access
Control) wird gesteuert, welche Kubernetes-API-Operationen ein Pod ausführen darf.

```yaml
# Role: Welche Operationen auf welchen Ressourcen?
kind: Role
rules:
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["create", "get", "list", "delete"]

# RoleBinding: Welcher ServiceAccount bekommt diese Role?
kind: RoleBinding
subjects:
  - kind: ServiceAccount
    name: api-gateway
```

**Least Privilege:** Der `api-gateway` ServiceAccount darf nur Jobs verwalten
und ConfigMaps lesen — keine Cluster-weiten Rechte.

---

## Quellen

- [Kubernetes Konzepte (offizielle Doku)](https://kubernetes.io/docs/concepts/)
- [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [RBAC Autorisierung](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)