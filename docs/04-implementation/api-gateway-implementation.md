# API Gateway - Implementation & Code Review

**Datum:** 08.02.2026 
**Status:** Code Review abgeschlossen, noch nicht deployed

---

## Übersicht

Das API Gateway ist der zentrale Einstiegspunkt für unsere Video Transcoding Platform. Es empfängt Video-Uploads, erstellt Kubernetes Jobs für das Transcoding und stellt Endpoints für Status-Abfragen und Downloads bereit.

### Architektur-Rolle

```
User/Frontend
    ↓ HTTP Request
API Gateway (FastAPI)
    ↓ Create Kubernetes Job
Transcoding Worker (FFmpeg Job)
    ↓ Process Video
Object Storage (später)
```

---

## 1. FastAPI Anwendung (main.py)

### 1.1 Was ist FastAPI?

**FastAPI** ist ein modernes Python Web-Framework mit folgenden Eigenschaften:

- **Async/Await Support**: Ideal für I/O-intensive Tasks (File-Uploads, API-Calls)
- **Automatische Validierung**: Type Hints werden zu automatischen Checks
- **Auto-Documentation**: Swagger UI unter `/docs` verfügbar
- **Performance**: Vergleichbar mit Node.js und Go

**Warum FastAPI für uns?**
- Video-Uploads sind I/O-intensiv → Async hilft
- Kubernetes API-Calls sind I/O → Async verhindert Blocking
- Built-in Docs → einfaches Testing
- Python → passt zu Data Science / ML Workflows

---

### 1.2 Application Setup

```python
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API Gateway for cloud-native video transcoding platform",
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)
```

**Was macht das?**

1. **title, version, description**: Metadaten für API-Dokumentation
2. **docs_url="/api/v1/docs"**: Swagger UI Endpoint
    - Interaktive API-Dokumentation
    - Direktes Testen von Endpoints
    - Automatisch generiert aus Code
3. **redoc_url="/api/v1/redoc"**: Alternative Dokumentation
    - Schöner, aber weniger interaktiv
    - Gut für externe API-Nutzer

**API Versioning (`/api/v1`)**

```
/api/v1/upload    ← Version 1
/api/v2/upload    ← Später: Version 2 mit Breaking Changes
```

**Vorteil:**
- Alte Clients können `/api/v1` nutzen
- Neue Features in `/api/v2` ohne alte zu brechen

---

### 1.3 CORS Middleware

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Was ist CORS?**

**Cross-Origin Resource Sharing** - Browser-Sicherheitsmechanismus.

**Problem ohne CORS:**
```
Browser (localhost:3000 - React Frontend)
    ↓ GET http://localhost:8080/api/v1/videos
    ↓
API (localhost:8080)
    ↓
Browser: ❌ BLOCKED!
Error: "CORS policy: No 'Access-Control-Allow-Origin' header"
```

**Warum blockiert?**
- Verschiedene Origins (Port 3000 vs. 8080)
- Browser-Sicherheit: Verhindert Cross-Site Scripting (XSS)

**Mit CORS Middleware:**
```python
allow_origins=["*"]  # API sagt: "Ich erlaube alle Origins"
```

API-Response bekommt Header:
```
Access-Control-Allow-Origin: *
```

Browser sieht Header → erlaubt Request.

**Security Note:**
- `["*"]` = Alle Origins (OK für Development/Testing)
- **Production**: `allow_origins=["https://frontend.example.com"]`
- **Warum?** Verhindert dass böse Websites deine API nutzen

**allow_credentials=True:**
- Erlaubt Cookies/Auth-Headers in Cross-Origin Requests
- Wichtig für Authentication später

---

### 1.4 Root Endpoint

```python
@app.get("/")
async def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": f"{settings.api_prefix}/docs",
        "health": f"{settings.api_prefix}/health",
    }
```

**Decorator `@app.get("/")`:**
- Registriert Funktion als Route Handler
- `"/"` = Root path (http://localhost:8080/)
- `get` = HTTP GET Method

**async def:**
- Asynchrone Funktion
- Kann andere async-Funktionen `await`-en
- Gibt Thread frei während Warten (I/O)

**Return:**
- Dict wird automatisch zu JSON
- FastAPI macht: `json.dumps(dict)` + Content-Type Header

**Test:**
```bash
curl http://localhost:8080/
# {
#   "service": "Video Transcoding API Gateway",
#   "version": "0.1.0",
#   "docs": "/api/v1/docs",
#   "health": "/api/v1/health"
# }
```

**Zweck:**
- Discovery: Nutzer sieht wo die Docs sind
- Health Check für Load Balancer
- Version Info

---

### 1.5 Startup Event

```python
@app.on_event("startup")
async def startup_event():
    import os
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.output_dir, exist_ok=True)
    print(f"🚀 {settings.app_name} started")
```

**Wann läuft das?**
- **Einmal** beim Container-Start
- **Vor** dem ersten Request

**Was macht es?**

1. **Erstellt Directories:**
   ```python
   os.makedirs("/tmp/uploads", exist_ok=True)
   os.makedirs("/tmp/outputs", exist_ok=True)
   ```
    - Container-Dateisystem ist leer beim Start
    - `exist_ok=True`: Kein Error wenn schon existiert

2. **Logging:**
    - Zeigt dass Service gestartet ist
    - Wichtig für Debugging in Kubernetes

**Warum wichtig?**
- Video-Uploads gehen nach `/tmp/uploads`
- Ordner muss existieren, sonst Error
- Alternative: Volume-Mount (kommt später)

**Später hier:**
- Database Connection Pool initialisieren
- Redis Connection aufbauen
- Kubernetes Client initialisieren

---

### 1.6 Shutdown Event

```python
@app.on_event("shutdown")
async def shutdown_event():
    print(f"👋 {settings.app_name} shutting down")
```

**Wann läuft das?**
- Beim Container-Stopp
- z.B. `kubectl delete pod` oder Rolling Update

**Warum wichtig?**
- Cleanup: Connections schließen
- Graceful Shutdown: Requests zu Ende bringen
- Logs für Debugging

**Später hier:**
- Database Connections schließen
- Redis Connections schließen
- Laufende Uploads abbrechen

---

## 2. Dockerfile - Multi-Stage Build

### 2.1 Warum Multi-Stage?

**Problem Single-Stage:**
```dockerfile
FROM python:3.11
RUN pip install pandas numpy scikit-learn
# → Image: 2GB (enthält Build-Tools, Compiler, etc.)
```

**Lösung Multi-Stage:**
```dockerfile
# Stage 1: Builder (hat Build-Tools)
FROM python:3.11 as builder
RUN pip install --user pandas

# Stage 2: Runtime (nur Laufzeit)
FROM python:3.11-slim
COPY --from=builder /root/.local /home/appuser/.local
# → Image: 500MB (nur Binaries, keine Build-Tools)
```

**Vorteil:**
- ✅ Kleinere Images (schnellerer Pull)
- ✅ Weniger Angriffsfläche (keine Compiler in Production)
- ✅ Schnelleres Deployment

---

### 2.2 Stage 1: Builder

```dockerfile
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt
```

**Zeile für Zeile:**

1. **`FROM python:3.11-slim as builder`**
    - Basis-Image: Python 3.11 auf Debian (minimale Variante)
    - `as builder`: Name dieser Stage (für COPY --from später)

2. **`WORKDIR /app`**
    - Setzt Arbeitsverzeichnis im Container
    - Alle weiteren Commands laufen in `/app`

3. **`COPY requirements.txt .`**
    - Kopiert `requirements.txt` vom Host → `/app/requirements.txt` im Container
    - `.` = Aktuelles Verzeichnis (`/app`)

4. **`RUN pip install --no-cache-dir --user -r requirements.txt`**
    - `--no-cache-dir`: Löscht Download-Cache → spart Speicher
    - `--user`: Installiert in `/root/.local` statt System-wide
    - `-r requirements.txt`: Installiert alle Packages aus Datei

**Warum erst requirements.txt, dann Code?**

Docker cached Layers:
```
COPY requirements.txt → Layer 1 (cached wenn requirements.txt unverändert)
RUN pip install      → Layer 2 (cached wenn Layer 1 cached)
COPY app/            → Layer 3 (neu bei Code-Änderung)
```

**Wenn du Code änderst:**
- Layer 3 wird neu gebaut
- Layer 1+2 bleiben gecached
- **Schnelleres Rebuild!**

---

### 2.3 Stage 2: Runtime

```dockerfile
FROM python:3.11-slim

RUN useradd -m -u 1000 appuser
WORKDIR /app
```

**Frisches Image:**
- Startet von `python:3.11-slim` (ohne Builder-Layer)
- Nur minimal nötig für Runtime

**Security: Non-Root User**

```dockerfile
RUN useradd -m -u 1000 appuser
```

- `useradd`: Linux-Befehl zum User erstellen
- `-m`: Home-Directory erstellen (`/home/appuser`)
- `-u 1000`: User-ID (Standard non-root)
- `appuser`: Username

**Warum nicht root?**

**Ohne:**
```
Container läuft als root (UID 0)
    ↓ Container kompromittiert
    ↓ Angreifer hat root-Rechte
    ❌ Kann Host-System angreifen
```

**Mit non-root:**
```
Container läuft als appuser (UID 1000)
    ↓ Container kompromittiert
    ↓ Angreifer hat nur User-Rechte
    ✅ Kann Host-System NICHT angreifen
```

**Best Practice:** Container = Least Privilege

---

### 2.4 Dependencies kopieren

```dockerfile
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local
```

**Was macht das?**

1. **`--from=builder`**: Kopiert aus Stage 1 (Builder)
2. **`--chown=appuser:appuser`**: Setzt Besitzer
    - Format: `user:group`
    - Wichtig: Files müssen appuser gehören
3. **`/root/.local`**: Wo pip --user installiert hat
4. **`/home/appuser/.local`**: Ziel im Runtime-Image

**Warum nur .local kopieren?**
- Builder hat viel unnötiges Zeug (Source-Files, Cache)
- Wir brauchen nur compiled Packages
- Spart hunderte MB

---

### 2.5 Code kopieren

```dockerfile
COPY --chown=appuser:appuser ./app ./app
```

- Kopiert `app/` Verzeichnis vom Host → `/app/app` im Container
- `--chown`: appuser besitzt die Files

---

### 2.6 PATH & User

```dockerfile
ENV PATH=/home/appuser/.local/bin:$PATH
USER appuser
```

**PATH erweitern:**
- Python-Packages installieren Commands in `.local/bin`
- z.B. `uvicorn` Binary
- PATH muss erweitert werden, sonst findet Shell es nicht

**USER appuser:**
- **Ab hier laufen alle Commands als appuser**
- `CMD` läuft als appuser (nicht root)
- Security!

---

### 2.7 Port & CMD

```dockerfile
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**EXPOSE 8000:**
- **Nur Dokumentation!** Öffnet Port nicht wirklich
- Sagt: "Dieser Container lauscht auf 8000"
- Kubernetes liest das für Container-Port

**CMD:**
- Befehl der beim Container-Start läuft
- `uvicorn`: ASGI-Server für FastAPI
- `app.main:app`: Python-Modul (`app/main.py`), Variable `app`
- `--host 0.0.0.0`: **Wichtig!** Lauscht auf allen Netzwerk-Interfaces
    - `127.0.0.1` (localhost) würde nicht von außen erreichbar sein
    - `0.0.0.0` = alle IPs des Containers
- `--port 8000`: Lauscht auf Port 8000

---

## 3. Kubernetes Deployment

### 3.1 Metadata & Labels

```yaml
metadata:
  name: api-gateway
  namespace: video-transcoding
  labels:
    app: api-gateway
    component: backend
    tier: api
```

**Labels - Warum 3?**

Organisationssystem wie Hashtags:

- **`app: api-gateway`**: Hauptidentifikation
    - Service nutzt das für Selector
    - `kubectl get pods -l app=api-gateway`

- **`component: backend`**: Logische Gruppierung
    - vs. `frontend`, `database`
    - `kubectl get pods -l component=backend`

- **`tier: api`**: Schicht-Modell
    - vs. `tier: data`, `tier: cache`
    - Für Netzwerk-Policies später

**Nutzen:**
```bash
# Alle Backend-Pods
kubectl get pods -l component=backend

# Alle API-Tier Pods (könnte mehrere Services umfassen)
kubectl get pods -l tier=api

# Nur API Gateway
kubectl get pods -l app=api-gateway
```

---

### 3.2 Replicas & Update Strategy

```yaml
replicas: 2

strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```

**Replicas: 2 - Warum?**

1. **High Availability:**
   ```
   Pod 1 stirbt → Pod 2 läuft weiter → Keine Downtime
   ```

2. **Load Balancing:**
   ```
   Request 1 → Pod 1
   Request 2 → Pod 2
   Request 3 → Pod 1
   ```

3. **Rolling Updates ohne Downtime:**
   ```
   Update: Pod 1 → v2, Pod 2 noch v1 → Traffic geht zu Pod 2
   Dann:   Pod 2 → v2, Pod 1 schon v2 → Traffic verteilt
   ```

**RollingUpdate Strategy:**

```
Start:    [Pod1 v1] [Pod2 v1]
             ↓
Schritt 1: [Pod1 v1] [Pod2 v1] [Pod3 v2]  ← maxSurge: 1
             ↓
Schritt 2: [Pod2 v1] [Pod3 v2]             ← Pod1 wird gelöscht
             ↓
Schritt 3: [Pod2 v1] [Pod3 v2] [Pod4 v2]  ← Neuer Pod
             ↓
Ende:      [Pod3 v2] [Pod4 v2]             ← Pod2 wird gelöscht
```

**Parameter:**
- `maxSurge: 1`: Max 1 Pod **mehr** als `replicas` während Update
    - Erlaubt: 3 Pods (2 + 1)
    - Braucht mehr Ressourcen temporär

- `maxUnavailable: 0`: **Minimum** 2 Pods müssen immer laufen
    - **Keine Downtime garantiert**
    - 0 = Alle Pods müssen immer verfügbar sein

**Alternative Strategien:**

- `Recreate`: Alle Pods löschen, dann neue erstellen
    - **Downtime!** Nur für Dev-Umgebungen

---

### 3.3 Service Account

```yaml
serviceAccountName: api-gateway
```

**Was ist ein ServiceAccount?**

Eine **Identity** für Pods innerhalb von Kubernetes.

**Analogie:**
```
User Account (für Menschen)
    ↓ kubectl get pods
Kubernetes API
    ✅ Hat Rechte

Service Account (für Pods)
    ↓ Kubernetes Client in Python
Kubernetes API
    ✅ Hat Rechte (wenn RBAC konfiguriert)
```

**Warum brauchen wir das?**

Unser API Gateway muss **Kubernetes Jobs erstellen**:

```python
# In Python später:
from kubernetes import client

job = client.V1Job(...)
batch_api.create_namespaced_job(
    namespace="video-transcoding",
    body=job
)
```

**Ohne ServiceAccount:**
```
Pod → Kubernetes API: "Create Job"
API: ❌ "Forbidden: No permissions"
```

**Mit ServiceAccount + RBAC:**
```
Pod (als api-gateway ServiceAccount)
    → Kubernetes API: "Create Job"
    → API prüft: ServiceAccount hat Role "job-creator"
    → Role erlaubt: Create Jobs in namespace "video-transcoding"
    ✅ Job wird erstellt
```

**RBAC = Role-Based Access Control**

Claude Code hat wahrscheinlich erstellt:
```yaml
# service-account.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-gateway
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: job-creator
rules:
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["create", "get", "list", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: api-gateway-job-creator
subjects:
- kind: ServiceAccount
  name: api-gateway
roleRef:
  kind: Role
  name: job-creator
```

---

### 3.4 Environment Variables

```yaml
env:
- name: APP_NAME
  value: "Video Transcoding API Gateway"

- name: KUBERNETES_NAMESPACE
  valueFrom:
    fieldRef:
      fieldPath: metadata.namespace

- name: IN_CLUSTER
  value: "true"
```

**Verschiedene Arten ENV-Vars:**

1. **Hardcoded:**
   ```yaml
   - name: DEBUG
     value: "false"
   ```
    - Einfach, aber nicht flexibel

2. **From Field (Downward API):**
   ```yaml
   - name: KUBERNETES_NAMESPACE
     valueFrom:
       fieldRef:
         fieldPath: metadata.namespace
   ```
    - Pod liest seine eigenen Metadaten
    - `metadata.namespace` → Pod weiß in welchem Namespace er läuft

**Warum wichtig?**

```python
# In Python:
namespace = os.getenv('KUBERNETES_NAMESPACE')
# → "video-transcoding"

# Job erstellen im gleichen Namespace:
batch_api.create_namespaced_job(
    namespace=namespace,  # Automatisch korrekt!
    body=job
)
```

**IN_CLUSTER:**
- Sagt Python Kubernetes-Client: "Du läufst in Cluster"
- Nutzt dann ServiceAccount-Token automatisch
- Alternative: `IN_CLUSTER=false` für lokales Testing

---

### 3.5 Resources

```yaml
resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

**Requests vs. Limits - Der Unterschied:**

| | Requests | Limits |
|---|----------|--------|
| **Bedeutung** | "Ich brauche mindestens..." | "Ich darf maximal..." |
| **Scheduling** | Pod nur auf Node wenn genug frei | Egal |
| **Garantie** | Ja, bekommt mindestens diese Ressourcen | Nein |
| **Überschreitung** | Impossible (ist garantiert) | CPU: Throttling, Memory: Kill |

**Beispiel:**

```yaml
requests:
  memory: "128Mi"
  cpu: "100m"
```

**Scheduling:**
```
Node A: 256Mi RAM frei, 500m CPU frei
    ↓ Pod braucht 128Mi, 100m
    ✅ Passt, wird gescheduled

Node B: 64Mi RAM frei, 1000m CPU frei
    ↓ Pod braucht 128Mi, aber nur 64Mi frei
    ❌ Passt nicht, Pod bleibt Pending
```

**Limits:**
```yaml
limits:
  memory: "512Mi"
  cpu: "500m"
```

**CPU Limit:**
- Pod nutzt 600m CPU (mehr als 500m Limit)
- → Kubernetes **drosselt** CPU auf 500m
- Pod läuft langsamer, aber stirbt nicht

**Memory Limit:**
- Pod nutzt 600Mi Memory (mehr als 512Mi Limit)
- → Kubernetes **killt** Pod
- Reason: `OOMKilled` (Out Of Memory)
- Pod wird neu gestartet

**Einheiten:**
- `128Mi` = 128 Mebibyte (2^20 bytes) ≈ 134 MB
- `100m` = 100 millicores = 0.1 CPU cores
- `1000m` = 1 CPU core

**Warum Request < Limit?**

```
Normal-Last: 128Mi → innerhalb Request, garantiert
Burst-Last:  400Mi → über Request, aber unter Limit, erlaubt
Leak/Bug:    600Mi → über Limit → Pod wird killed
```

**Best Practice:**
- Request: Was du **normalerweise** brauchst
- Limit: Was du **maximal** tolerierst (Sicherheitsnetz)

---

### 3.6 Liveness Probe

```yaml
livenessProbe:
  httpGet:
    path: /api/v1/health
    port: http
  initialDelaySeconds: 10
  periodSeconds: 30
  timeoutSeconds: 5
  failureThreshold: 3
```

**Was ist Liveness?**

**Frage:** "Lebst du noch?"

**Zweck:** Container neu starten wenn er "hängt".

**Ablauf:**

```
Container startet
    ↓ (warte 10 Sekunden - initialDelaySeconds)
kubelet: GET /api/v1/health
    ↓ (200 OK in < 5 Sekunden?)
    ✅ Healthy
    ↓ (warte 30 Sekunden - periodSeconds)
kubelet: GET /api/v1/health
    ↓ (500 Error oder Timeout?)
    ⚠️ Failure 1/3
    ↓ (warte 30 Sekunden)
kubelet: GET /api/v1/health
    ↓ (Timeout?)
    ⚠️ Failure 2/3
    ↓ (warte 30 Sekunden)
kubelet: GET /api/v1/health
    ↓ (Timeout?)
    ❌ Failure 3/3 → RESTART CONTAINER
```

**Parameter:**

- `initialDelaySeconds: 10`: Warte 10 Sek nach Start
    - App braucht Zeit zum Booten
    - Zu kurz → False-Positive Restarts

- `periodSeconds: 30`: Prüfe alle 30 Sekunden
    - Nicht zu oft (unnötige Last)
    - Nicht zu selten (langsame Erkennung)

- `timeoutSeconds: 5`: Max 5 Sek für Response
    - Länger → gilt als Failure

- `failureThreshold: 3`: 3 Failures → Restart
    - Verhindert Restart bei kurzen Hickups

**Use Cases:**

✅ **Deadlock:** Thread hängt, Server reagiert nicht → Restart
✅ **Memory Leak:** App wird langsam, /health timeout → Restart
✅ **Database Connection Lost:** App funktioniert nicht → Restart

---

### 3.7 Readiness Probe

```yaml
readinessProbe:
  httpGet:
    path: /api/v1/ready
    port: http
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

**Was ist Readiness?**

**Frage:** "Bist du bereit für Traffic?"

**Unterschied zu Liveness:**

| | Liveness | Readiness |
|---|----------|-----------|
| **Frage** | Lebst du? | Bereit für Traffic? |
| **Bei Failure** | Container restart | Aus Service entfernen |
| **Zweck** | Hängende Container fixen | Kein Traffic zu nicht-bereiten Pods |

**Use Case:**

```
Pod startet
    ↓ Lädt große Config-Datei (10 Sekunden)
    ↓ Readiness: Not Ready
    ↓ Service: Sendet KEINEN Traffic zu diesem Pod
    ↓
Config geladen
    ↓ Readiness: Ready
    ↓ Service: Sendet Traffic zu diesem Pod
```

**Warum beide Probes?**

```
Pod hat temporäres Problem (DB-Connection lost)
    ↓ Readiness fails → Kein Traffic
    ↓ (wartet auf DB-Reconnect)
    ↓ Readiness succeeds → Traffic wieder
    ↓ Liveness war die ganze Zeit OK → Kein Restart
```

**Beispiel Rolling Update:**

```
Update: Neuer Pod startet
    ↓ Readiness: Not Ready (startet noch)
    ↓ Service: Sendet Traffic zu alten Pods
    ↓
Neuer Pod: Ready
    ↓ Service: Sendet Traffic zu neuem + alten Pods
    ↓
Alter Pod: Wird gelöscht
    ↓ Service: Sendet nur noch Traffic zu neuem Pod
```

**Zero-Downtime!**

---

### 3.8 Volumes

```yaml
volumeMounts:
- name: uploads
  mountPath: /tmp/uploads
- name: outputs
  mountPath: /tmp/outputs

volumes:
- name: uploads
  emptyDir:
    sizeLimit: 10Gi
- name: outputs
  emptyDir:
    sizeLimit: 10Gi
```

**Was ist emptyDir?**

- **Temporäres** Verzeichnis
- Erstellt wenn Pod startet
- **Gelöscht** wenn Pod stirbt
- Geteilt zwischen Containern im Pod

**Lifecycle:**

```
Pod startet
    → emptyDir erstellt (leer)
    → Container schreibt Dateien
    → Dateien bleiben während Pod läuft
    → Pod stirbt
    → emptyDir wird GELÖSCHT
```

**Warum emptyDir für Videos?**

❌ **NICHT für finale Videos!**
- Pod stirbt → Videos weg
- Nur für **temporäre** Verarbeitung

**Flow:**

```
1. Video-Upload → /tmp/uploads/video.mp4 (emptyDir)
2. Transcoding → liest von /tmp/uploads
3. Output → schreibt nach /tmp/outputs/video-720p.mp4 (emptyDir)
4. Upload to S3 → von /tmp/outputs
5. Delete aus emptyDir → Speicher frei
```

**sizeLimit: 10Gi:**
- Max 10 Gigabyte
- Verhindert dass Pod ganzen Node-Speicher füllt
- Über Limit → Pod wird evicted (aus Node geworfen)

**Später:**
- **PersistentVolume** für dauerhafte Speicherung
- **S3/MinIO** für Object Storage
- emptyDir nur für Temp-Files

---

## 4. Kubernetes Service

```yaml
type: ClusterIP

selector:
  app: api-gateway

ports:
- name: http
  protocol: TCP
  port: 80
  targetPort: http
```

**Was macht ein Service?**

**Problem ohne Service:**

```
Client will API aufrufen
    → Welche Pod-IP?
    → Pod 1: 10.244.1.5
    → Pod 2: 10.244.2.8
    → Pod stirbt → neue IP!
```

**Lösung mit Service:**

```
Client → Service (10.96.87.61 - stabile IP)
    → Load Balancer
    → Pod 1 (10.244.1.5)
    → Pod 2 (10.244.2.8)
```

**Service DNS:**
```
api-gateway.video-transcoding.svc.cluster.local
```

Von anderem Pod im Cluster:
```bash
curl http://api-gateway.video-transcoding.svc.cluster.local
# oder kurz:
curl http://api-gateway
```

**ClusterIP:**
- Nur innerhalb Cluster erreichbar
- **NICHT** von außen (deinem Browser)

**Für External Access (später):**
- **Ingress** (HTTP/S Routing)
- **NodePort** (Port auf allen Nodes)
- **LoadBalancer** (Cloud Load Balancer)

**Ports:**

```yaml
port: 80          # Service lauscht auf Port 80
targetPort: http  # Leitet zu Container-Port "http" (8000)
```

**Flow:**

```
Request → Service:80 → Load Balancer → Pod:8000
```

**targetPort: http** referenziert:
```yaml
# In Deployment:
ports:
- name: http      # ← Dieser Name
  containerPort: 8000
```

---

## 5. Was haben wir erreicht?

### Code

✅ **FastAPI App** mit:
- Root Endpoint (/)
- Health Endpoints (/api/v1/health, /api/v1/ready)
- CORS für Frontend-Zugriff
- Startup/Shutdown Events
- Settings-Management

### Docker

✅ **Multi-Stage Dockerfile** mit:
- Builder Stage (Dependencies installieren)
- Runtime Stage (nur Runtime-Binaries)
- Non-Root User (Security)
- Optimierte Layer (schnelles Rebuild)

### Kubernetes

✅ **Deployment** mit:
- 2 Replicas (High Availability)
- Rolling Updates (Zero Downtime)
- Health Probes (Self-Healing)
- Resource Limits (Cluster Protection)
- ServiceAccount (API-Zugriff)

✅ **Service** mit:
- Load Balancing
- Stabile IP/DNS
- Port-Mapping

---

## 6. Was fehlt noch?

### Funktionalität

❌ Upload Endpoint (`POST /api/v1/upload`)
❌ Job Controller (Kubernetes Job erstellen)
❌ Status Endpoint (`GET /api/v1/jobs/{id}`)
❌ Download Endpoint (`GET /api/v1/download/{id}`)

### Testing

❌ Docker Image bauen
❌ Image in Kind laden
❌ Kubernetes Manifests anwenden
❌ Functionality Tests

### Storage

❌ Persistent Storage (PV/PVC)
❌ Object Storage (MinIO/S3)
❌ Database (PostgreSQL für Metadata)

---

## 7. Nächste Schritte

### Phase 1: Deployment (Jetzt)

1. Docker Image bauen
2. Image in Kind-Cluster laden
3. ServiceAccount + RBAC erstellen
4. Deployment anwenden
5. Service anwenden
6. Port-Forward testen
7. Health Endpoints testen

### Phase 2: Upload Feature

1. Upload Endpoint implementieren
2. File Validation (Format, Size)
3. Temporary Storage (emptyDir)
4. Testing

### Phase 3: Job Controller

1. Kubernetes Job Template
2. Job-Erstellung aus API
3. Job Status Monitoring
4. Cleanup

### Phase 4: Transcoding Worker

1. FFmpeg Container
2. Job Implementation
3. Input/Output Handling
4. Testing

---

## 8. Learnings & Best Practices

### FastAPI

✅ Async/Await für I/O-intensive Tasks
✅ Auto-Documentation spart Entwicklungszeit
✅ CORS Middleware für Frontend-Integration
✅ Startup Events für Initialisierung

### Docker

✅ Multi-Stage Builds = kleinere Images
✅ Non-Root User = Security
✅ Layer-Optimierung = schnelleres Rebuild
✅ `--no-cache-dir` = weniger Speicher

### Kubernetes

✅ 2+ Replicas = High Availability
✅ RollingUpdate + Probes = Zero Downtime
✅ Resource Limits = Cluster Protection
✅ ServiceAccount = Least Privilege
✅ Labels = Flexibles Organisieren

### Architecture

✅ API Versioning (/api/v1) = Abwärtskompatibilität
✅ Health Endpoints = Monitoring & Orchestration
✅ Settings-Management = Umgebungs-Flexibilität
✅ Separation of Concerns = Wartbarkeit

---

**Erstellt:** 08.02.2026
**Status:** Code Review abgeschlossen, bereit für Deployment-Test