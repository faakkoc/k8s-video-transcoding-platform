# API Gateway Service

**Datum:** 08.02.2026
**Status:** In Entwicklung

---

## Überblick

Das API Gateway ist der zentrale Einstiegspunkt für die Video Transcoding Platform. Es ist ein FastAPI-basierter REST-Service, der folgende Aufgaben übernimmt:

- **Video-Upload**: Empfängt Video-Dateien von Clients
- **Job-Management**: Erstellt Kubernetes Jobs für Transcoding-Tasks
- **Status-Monitoring**: Verfolgt den Fortschritt der Transcoding-Jobs
- **Result-Download**: Stellt fertig transcodierte Videos bereit

---

## Architektur

```
┌─────────┐       ┌──────────────┐       ┌────────────────┐
│ Client  │──────▶│ API Gateway  │──────▶│ Kubernetes API │
│ (Web)   │       │  (FastAPI)   │       │  (Create Jobs) │
└─────────┘       └──────────────┘       └────────────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │   Storage    │
                  │ (Filesystem) │
                  └──────────────┘
```

### Warum FastAPI?

**FastAPI** wurde gewählt, weil:
- **Async/Await**: Perfekt für I/O-intensive Operationen (File-Upload)
- **Type Hints**: Automatische Validierung und API-Dokumentation
- **Performance**: Vergleichbar mit Node.js und Go
- **Auto-Dokumentation**: Interaktive API-Docs unter `/docs` (Swagger UI)
- **Python-Ecosystem**: Einfache Integration mit Kubernetes Python Client

---

## Tech Stack

| Komponente | Version | Zweck |
|------------|---------|-------|
| **FastAPI** | 0.109.0 | Web-Framework |
| **Uvicorn** | 0.27.0 | ASGI Server (async) |
| **Kubernetes Client** | 29.0.0 | Kubernetes API (Jobs erstellen) |
| **Pydantic** | 2.5.3 | Datenvalidierung |
| **aiofiles** | 23.2.1 | Async File I/O |

---

## Projektstruktur

```
api-gateway/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI Application
│   ├── config.py            # Konfiguration (Environment Variables)
│   ├── routers/
│   │   ├── __init__.py
│   │   └── health.py        # Health Check Endpoints
│   ├── models/              # Pydantic Models (Request/Response)
│   │   └── __init__.py
│   └── utils/               # Hilfs-Funktionen
│       └── __init__.py
├── tests/                   # Unit & Integration Tests
│   └── __init__.py
├── Dockerfile               # Multi-Stage Production Image
├── .dockerignore
├── requirements.txt         # Python Dependencies
└── README.md               # Diese Datei
```

---

## Entwicklungsumgebung Setup

### Voraussetzungen

- Python 3.11+
- Docker Desktop
- kubectl
- Kind-Cluster (siehe `scripts/setup-kind.sh`)

### Lokale Entwicklung (ohne Kubernetes)

```bash
# Ins Verzeichnis wechseln
cd services/api-gateway

# Virtual Environment erstellen
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Dependencies installieren
pip install -r requirements.txt

# Environment Variables setzen (optional)
export IN_CLUSTER=false
export DEBUG=true

# Anwendung starten
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Was macht `--reload`?**
- Überwacht Code-Änderungen
- Startet Server automatisch neu
- Nur für Development (nicht in Production!)

**Zugriff:**
- **API Dokumentation**: http://localhost:8000/api/v1/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8000/api/v1/redoc (ReDoc)
- **Health Check**: http://localhost:8000/api/v1/health
- **Readiness**: http://localhost:8000/api/v1/ready

---

## Docker Image bauen

### Warum Multi-Stage Build?

Unser Dockerfile nutzt **Multi-Stage Build**:

```dockerfile
# Stage 1: Builder (mit gcc für native Extensions)
FROM python:3.11-slim as builder
# ... Dependencies installieren

# Stage 2: Runtime (minimal, nur was zum Laufen nötig ist)
FROM python:3.11-slim
# ... nur fertige Dependencies kopieren
```

**Vorteile:**
- **Kleineres Image**: Build-Tools (gcc) nicht im finalen Image
- **Schnellere Deploys**: Weniger MB zum übertragen
- **Sicherer**: Weniger Attack Surface (keine Build-Tools in Production)

### Image bauen und testen

```bash
# Ins Verzeichnis wechseln
cd services/api-gateway

# Image bauen
docker build -t api-gateway:latest .

# Container lokal starten
docker run -p 8000:8000 api-gateway:latest

# In anderem Terminal: Health Check testen
curl http://localhost:8000/api/v1/health
```

### Image in Kind-Cluster laden

**Wichtig:** Kind-Cluster ist isoliert und sieht lokale Docker-Images nicht automatisch!

```bash
# Image in Kind laden
kind load docker-image api-gateway:latest --name video-transcoding

# Verifizieren (im Control-Plane Node)
docker exec -it video-transcoding-control-plane crictl images | grep api-gateway
```

**Was passiert intern?**
1. Kind liest Image aus lokalem Docker
2. Kopiert es in **jeden Node** des Clusters
3. Speichert es in containerd (Container-Runtime im Node)

---

## Kubernetes Deployment

### Voraussetzungen

```bash
# Cluster läuft?
kubectl get nodes

# Namespace existiert?
kubectl get namespace video-transcoding
```

Falls nicht:
```bash
./scripts/setup-kind.sh
```

### Manifests anwenden

```bash
# Alle Manifests auf einmal
kubectl apply -f kubernetes/local/api-gateway/

# Oder einzeln (in dieser Reihenfolge):
kubectl apply -f kubernetes/local/api-gateway/service-account.yaml
kubectl apply -f kubernetes/local/api-gateway/deployment.yaml
kubectl apply -f kubernetes/local/api-gateway/service.yaml
kubectl apply -f kubernetes/local/api-gateway/hpa.yaml
```

**Reihenfolge wichtig?**
- `service-account.yaml` **zuerst**: Deployment referenziert ServiceAccount
- Rest kann parallel angewendet werden

### Deployment verifizieren

```bash
# Alle Ressourcen anzeigen
kubectl get all -n video-transcoding -l app=api-gateway

# Erwartete Ausgabe:
# NAME                              READY   STATUS    RESTARTS   AGE
# pod/api-gateway-xxxxx-aaaaa       1/1     Running   0          1m
# pod/api-gateway-xxxxx-bbbbb       1/1     Running   0          1m
#
# NAME                  TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
# service/api-gateway   ClusterIP   10.96.123.45    <none>        80/TCP    1m
#
# NAME                          READY   UP-TO-DATE   AVAILABLE   AGE
# deployment.apps/api-gateway   2/2     2            2           1m

# Logs anschauen
kubectl logs -n video-transcoding -l app=api-gateway --tail=50 -f

# Port-Forward für lokalen Zugriff
kubectl port-forward -n video-transcoding svc/api-gateway 8080:80
```

**Zugriff:** http://localhost:8080/api/v1/docs

---

## Erklärung der Kubernetes Manifests

### 1. Deployment (`deployment.yaml`)

#### Replicas

```yaml
replicas: 2
```

**Warum 2 Replicas?**
- **High Availability**: Wenn ein Pod stirbt, ist der andere noch da
- **Load Balancing**: Traffic wird auf beide Pods verteilt
- **Rolling Update**: Mindestens 1 Pod bleibt während Update verfügbar

#### Rolling Update Strategy

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1        # Max 1 extra Pod während Update
    maxUnavailable: 0  # Kein Pod darf unavailable sein
```

**Was bedeutet das?**
```
Vorher:  [Pod v1] [Pod v1]
           ↓
Schritt 1: [Pod v1] [Pod v1] [Pod v2]  (maxSurge: +1)
           ↓
Schritt 2: [Pod v1] [Pod v2]           (alten Pod entfernt)
           ↓
Schritt 3: [Pod v1] [Pod v2] [Pod v2]  (maxSurge: +1)
           ↓
Nachher:  [Pod v2] [Pod v2]
```

**Ergebnis:** Zero-Downtime Deployment!

#### Resource Requests & Limits

```yaml
resources:
  requests:      # Minimum-Garantie
    memory: "128Mi"
    cpu: "100m"
  limits:        # Maximum-Grenze
    memory: "512Mi"
    cpu: "500m"
```

**Was bedeutet das?**

- **Requests** ("Ich brauche mindestens..."):
  - Kubernetes scheduled Pod nur auf Nodes mit genug freien Resources
  - `100m` = 0.1 CPU Cores (1000m = 1 voller Core)
  - Pod bekommt diese Resources garantiert

- **Limits** ("Ich darf maximal..."):
  - Container wird bei CPU-Limit gedrosselt (throttled)
  - Bei Memory-Überschreitung: Pod wird killed (OOMKilled)

**Warum beides?**
- Verhindert "Noisy Neighbors" (ein Pod frisst alle Resources)
- Ermöglicht effizientes Bin-Packing (viele Pods auf einem Node)

#### Health Probes

```yaml
livenessProbe:       # Ist der Container noch am Leben?
  httpGet:
    path: /api/v1/health
    port: http
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:      # Ist der Container bereit für Traffic?
  httpGet:
    path: /api/v1/ready
    port: http
  initialDelaySeconds: 5
  periodSeconds: 10
```

**Liveness vs. Readiness - Was ist der Unterschied?**

| Probe | Frage | Bei Failure | Use Case |
|-------|-------|-------------|----------|
| **Liveness** | "Lebst du noch?" | Container wird **neugestartet** | Deadlocks, Crashes |
| **Readiness** | "Bist du bereit?" | Pod bekommt **keinen Traffic** | Langsamer Start, Dependencies |

**Beispiel-Ablauf:**
```
Start → Readiness fails → Pod bekommt keinen Traffic
     → Readiness succeeds → Pod bekommt Traffic
     → App hängt sich auf → Liveness fails → Pod wird neugestartet
```

### 2. Service (`service.yaml`)

```yaml
type: ClusterIP
selector:
  app: api-gateway
ports:
- port: 80           # Port des Services
  targetPort: http   # Port des Containers (8000)
```

**Was macht der Service?**

- **ClusterIP**: Service ist nur **innerhalb** des Clusters erreichbar
- **Selector**: Alle Pods mit Label `app=api-gateway` gehören zu diesem Service
- **Load Balancing**: Traffic wird automatisch auf alle Pods verteilt (Round-Robin)

**Service Discovery:**
```bash
# Von einem anderen Pod im Cluster:
curl http://api-gateway.video-transcoding.svc.cluster.local:80

# Oder kurz (im gleichen Namespace):
curl http://api-gateway:80
```

**Für externen Zugriff:**
- Development: `kubectl port-forward`
- Production: Ingress oder LoadBalancer

### 3. ServiceAccount & RBAC (`service-account.yaml`)

#### Warum brauchen wir einen ServiceAccount?

Das API Gateway muss **Kubernetes Jobs erstellen**. Dafür braucht es Permissions!

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-gateway
```

**ServiceAccount** = "User-Account" für Pods (nicht für Menschen)

#### RBAC (Role-Based Access Control)

```yaml
kind: Role
rules:
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["create", "get", "list", "watch", "delete"]
```

**Was bedeutet das?**
- **apiGroups: ["batch"]**: Jobs gehören zur "batch" API-Gruppe
- **resources: ["jobs"]**: Wir wollen Jobs verwalten
- **verbs**: Welche Aktionen sind erlaubt?
  - `create`: Neue Jobs erstellen
  - `get`, `list`, `watch`: Job-Status abfragen
  - `delete`: Alte Jobs aufräumen

**Warum nicht Admin-Rechte?**
- **Principle of Least Privilege**: Nur minimal nötige Permissions
- **Security**: Wenn API Gateway kompromittiert wird, kann er nicht den ganzen Cluster übernehmen

### 4. Horizontal Pod Autoscaler (`hpa.yaml`)

```yaml
minReplicas: 2
maxReplicas: 10
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      averageUtilization: 70  # Scale up bei CPU > 70%
```

**Was macht der HPA?**

- Überwacht CPU und Memory der Pods
- Wenn CPU > 70%: Mehr Pods starten (Scale Up)
- Wenn CPU < 70%: Pods reduzieren (Scale Down)
- Bleibt zwischen 2-10 Pods

**Scaling-Verhalten:**

```yaml
scaleUp:
  stabilizationWindowSeconds: 0  # Schnell hochskalieren
scaleDown:
  stabilizationWindowSeconds: 300  # Langsam runterskalieren (5 Min)
```

**Warum asymmetrisch?**
- **Scale Up schnell**: Traffic-Spike → sofort mehr Kapazität
- **Scale Down langsam**: Verhindert "Flapping" (rauf-runter-rauf)

---

## API Endpoints

### Aktuell implementiert

| Method | Endpoint | Beschreibung |
|--------|----------|--------------|
| GET | `/` | API-Informationen |
| GET | `/api/v1/health` | Liveness Probe |
| GET | `/api/v1/ready` | Readiness Probe |

### Noch zu implementieren

| Method | Endpoint | Beschreibung |
|--------|----------|--------------|
| POST | `/api/v1/upload` | Video-Datei hochladen |
| GET | `/api/v1/jobs` | Alle Jobs auflisten |
| GET | `/api/v1/jobs/{job_id}` | Job-Status abfragen |
| GET | `/api/v1/download/{job_id}` | Transcodiertes Video herunterladen |
| DELETE | `/api/v1/jobs/{job_id}` | Job löschen |

---

## Konfiguration

Alle Einstellungen werden über **Environment Variables** gesteuert:

| Variable | Default | Beschreibung |
|----------|---------|--------------|
| `APP_NAME` | Video Transcoding API Gateway | Anwendungsname |
| `APP_VERSION` | 0.1.0 | Version |
| `DEBUG` | false | Debug-Modus |
| `API_PREFIX` | /api/v1 | API-Route-Prefix |
| `KUBERNETES_NAMESPACE` | video-transcoding | K8s Namespace |
| `IN_CLUSTER` | true | Läuft in K8s? |
| `MAX_UPLOAD_SIZE_MB` | 500 | Max. Video-Größe |
| `TRANSCODING_WORKER_IMAGE` | transcoding-worker:latest | Worker-Image |

**Wie werden sie gesetzt?**

- **Lokal**: `.env` Datei oder `export VAR=value`
- **Kubernetes**: ConfigMaps oder direkt im Deployment

---

## Testing

```bash
# Tests ausführen
pytest tests/

# Mit Coverage
pytest --cov=app tests/

# Spezifischen Test
pytest tests/test_health.py -v
```

---

## Troubleshooting

### Problem: Pod startet nicht

```bash
# Pod-Status prüfen
kubectl describe pod -n video-transcoding -l app=api-gateway

# Häufige Ursachen:
# - Image nicht in Kind geladen: kind load docker-image ...
# - Falscher imagePullPolicy: Muss IfNotPresent sein
# - Resource Requests zu hoch: Node hat nicht genug freie Resources
```

### Problem: "Permission denied" beim Job erstellen

```bash
# ServiceAccount und RBAC prüfen
kubectl get serviceaccount -n video-transcoding api-gateway
kubectl get role -n video-transcoding api-gateway-role
kubectl get rolebinding -n video-transcoding api-gateway-rolebinding

# Falls fehlend:
kubectl apply -f kubernetes/local/api-gateway/service-account.yaml
```

### Problem: Health Check schlägt fehl

```bash
# Port-Forward und manuell testen
kubectl port-forward -n video-transcoding svc/api-gateway 8080:80
curl http://localhost:8080/api/v1/health

# Logs checken
kubectl logs -n video-transcoding -l app=api-gateway --tail=100
```

### Problem: Falsches Image wird verwendet

```bash
# Aktuelles Image im Deployment prüfen
kubectl get deployment -n video-transcoding api-gateway -o jsonpath='{.spec.template.spec.containers[0].image}'

# Pods neu starten (pullt Image neu)
kubectl rollout restart deployment/api-gateway -n video-transcoding
```

---

## Nächste Schritte

1. **Upload Endpoint**: Video-Upload Funktionalität implementieren
2. **Job Controller**: Kubernetes Job-Erstellung für Transcoding
3. **Status Tracking**: Job-Status abfragen und speichern
4. **Download Endpoint**: Transcodierte Videos bereitstellen
5. **Storage Integration**: MinIO oder S3 statt Filesystem
6. **Database**: PostgreSQL für Job-Metadata
7. **Message Queue**: RabbitMQ für asynchrone Verarbeitung

---

## Quellen

- [FastAPI Dokumentation](https://fastapi.tiangolo.com/)
- [Kubernetes Python Client](https://github.com/kubernetes-client/python)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)

---

**Erstellt:** 08.02.2026
**Status:** Basis-Setup abgeschlossen, weitere Features folgen
