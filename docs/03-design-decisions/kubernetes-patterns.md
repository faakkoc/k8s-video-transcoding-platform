# Kubernetes-Patterns: Jobs, Deployments, RBAC und Image-Distribution

**Datum:** 19.04.2026  
**Status:** Abgeschlossen

---

## Jobs vs. Deployments

Kubernetes bietet verschiedene Workload-Typen. Die Wahl des richtigen Typs ist entscheidend für eine saubere Architektur.

### Deployments — für Long-running Services

Ein Deployment beschreibt den gewünschten Dauerzustand einer Anwendung. Kubernetes sorgt dafür, dass immer die gewünschte Anzahl an Replicas läuft.

**Verwendet für:** API Gateway

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  replicas: 2           # Immer 2 Pods laufen
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1       # Max 1 extra Pod während Update
      maxUnavailable: 0 # Kein Pod darf ausfallen
```

**Eigenschaften:**
- Läuft dauerhaft (24/7)
- Automatischer Neustart bei Failure
- Rolling Updates ohne Downtime
- Horizontal Pod Autoscaler (HPA) für automatische Skalierung

### Jobs — für Batch-Workloads

Ein Job läuft bis zur erfolgreichen Completion und beendet sich dann. Kubernetes tracked den Fortschritt und führt Retries bei Failure durch.

**Verwendet für:** Transcoding Worker

```yaml
apiVersion: batch/v1
kind: Job
spec:
  completions: 1        # Erfolgreich wenn 1 Pod succeeded
  parallelism: 1        # Nur 1 Pod gleichzeitig
  backoff_limit: 3      # Max 3 Retry-Versuche
  ttl_seconds_after_finished: 86400  # Cleanup nach 24h
```

**Eigenschaften:**
- Läuft einmalig, dann Exit
- Automatische Retries bei Failure (backoff_limit)
- Completion-Tracking
- Ressourcen werden nach Completion freigegeben

### Warum Jobs für Transcoding?

Video-Transcoding ist ein klassischer Batch-Job:

- Hat einen definierten Start- und Endpunkt
- Endet mit Exit 0 (Erfolg) oder Exit 1 (Fehler)
- Braucht keine dauerhafte Verfügbarkeit
- Ressourcen sollten nach Abschluss freigegeben werden

Ein Deployment wäre falsch, weil es den Worker-Container dauerhaft laufen lassen würde — ohne Arbeit, nur Ressourcen verbrauchend.

**Skalierung bei mehreren Jobs:**

```
Upload 1 → Job 1 → Worker Pod 1 ┐
Upload 2 → Job 2 → Worker Pod 2 ├─ Parallel auf verfügbaren Nodes
Upload 3 → Job 3 → Worker Pod 3 ┘
Upload 4 → Job 4 → Worker Pod 4 (Pending bis Node frei)
```

Kubernetes scheduled die Pods automatisch auf verfügbare Nodes. Kein manuelles Queue-Management nötig.

---

## RBAC: Least Privilege Principle

Der API Gateway muss Kubernetes Jobs erstellen — dafür braucht er Permissions auf die Kubernetes API. RBAC (Role-Based Access Control) ermöglicht präzise Berechtigungssteuerung.

### ServiceAccount

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-gateway
  namespace: video-transcoding
```

Jeder Pod läuft unter einem ServiceAccount. Ohne explizite Zuweisung nutzt er den `default` ServiceAccount ohne Permissions.

### Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: api-gateway-role
rules:
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["create", "get", "list", "watch", "delete"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
```

**Warum so restriktiv?**

```
Falsch (zu permissiv):
  apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]        # Admin-Rechte — gefährlich!

Richtig (minimal):
  apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["create", "get", "list", "watch", "delete"]
```

Das Principle of Least Privilege bedeutet: Nur die Permissions vergeben, die tatsächlich benötigt werden. Wenn der API Gateway kompromittiert wird, kann ein Angreifer nur Jobs verwalten — nicht den gesamten Cluster.

### In-Cluster Authentication

Wenn der API Gateway Pod läuft, erkennt der Kubernetes Python Client automatisch den ServiceAccount-Token:

```python
try:
    config.load_incluster_config()   # Nutzt ServiceAccount Token
except config.ConfigException:
    config.load_kube_config()        # Fallback für lokale Entwicklung
```

Der Token wird automatisch von Kubernetes in den Pod gemountet (`/var/run/secrets/kubernetes.io/serviceaccount/token`). Kein manuelles Credentials-Management nötig.

---

## Image-Distribution: kind load vs. Registry

### Lokale Entwicklung: kind load

Kind-Cluster sind isoliert — sie sehen lokale Docker-Images nicht automatisch. Images müssen explizit in den Cluster geladen werden:

```bash
docker build -t api-gateway:latest services/api-gateway/
kind load docker-image api-gateway:latest --name video-transcoding
```

`kind load` kopiert das Image in jeden Node des Clusters (containerd).

**Problem mit `:latest` Tag:**

Kind cached Images aggressiv. Bei Updates mit dem `:latest` Tag kann es vorkommen, dass die alte Version weiterläuft. Lösung: `imagePullPolicy: IfNotPresent` kombiniert mit `kubectl rollout restart` nach dem Image-Load.

**Warum keine lokale Registry?**

Ein Registry-Ansatz (`localhost:5001`, `kind-registry:5000`) wurde evaluiert und verworfen. Er bringt zusätzliche Komplexität (Registry-Container, containerd-Patches, DNS-Konfiguration) ohne Mehrwert für die lokale Entwicklung. `kind load` funktioniert zuverlässig und ist einfacher.

### Production: Container Registry

In der Cloud-Umgebung werden Images in einer Registry verwaltet:

| Umgebung | Registry |
|----------|----------|
| GCP | Google Artifact Registry |
| StackIT | StackIT Container Registry |

```bash
# GCP Beispiel:
docker build -t europe-west3-docker.pkg.dev/PROJECT/transcoding/api-gateway:v1.0.0 .
docker push europe-west3-docker.pkg.dev/PROJECT/transcoding/api-gateway:v1.0.0
```

**Vorteile gegenüber kind load:**
- Versionierte Tags (Semver) statt `:latest`
- CI/CD Pipeline pusht automatisch nach jedem Commit
- Images werden genau einmal gebaut, dann mehrfach verwendet
- Rollback auf frühere Versionen möglich

---

## Health Probes: Self-Healing

Kubernetes überwacht Container-Gesundheit über zwei Probe-Typen:

### Liveness Probe

Fragt: "Lebt der Container noch?" Bei Failure: Container wird neu gestartet.

```yaml
livenessProbe:
  httpGet:
    path: /api/v1/health
    port: http
  initialDelaySeconds: 10  # Warte 10s nach Start
  periodSeconds: 30         # Prüfe alle 30s
  failureThreshold: 3       # 3 Failures → Restart
```

**Anwendungsfall:** Deadlocks, Memory Leaks, hängende Prozesse.

### Readiness Probe

Fragt: "Ist der Container bereit für Traffic?" Bei Failure: Pod wird aus dem Service-Load-Balancer entfernt.

```yaml
readinessProbe:
  httpGet:
    path: /api/v1/ready
    port: http
  initialDelaySeconds: 5
  periodSeconds: 10
```

**Anwendungsfall:** Langsamer Start, externe Dependencies nicht bereit.

**Zusammenspiel bei Rolling Updates:**

```
Neuer Pod startet
    ↓ Readiness Probe: Not Ready
    ↓ Service sendet Traffic nur zu alten Pods
    ↓ Pod ist vollständig gestartet
    ↓ Readiness Probe: Ready
    ↓ Service verteilt Traffic auf neuen + alte Pods
    ↓ Alter Pod wird gelöscht
    ↓ Zero Downtime ✅
```

---

## Resource Requests und Limits

Kubernetes nutzt Resource Requests und Limits für Scheduling und Schutz:

| | Requests | Limits |
|---|----------|--------|
| **Bedeutung** | Minimum-Garantie | Maximum-Grenze |
| **Scheduling** | Node braucht min. diese freien Ressourcen | Egal |
| **CPU-Überschreitung** | Impossible | Throttling |
| **Memory-Überschreitung** | Impossible | OOMKilled → Restart |

**API Gateway (I/O-bound):**

```yaml
requests: { memory: "128Mi", cpu: "100m" }
limits:   { memory: "512Mi", cpu: "500m" }
```

**Transcoding Worker (CPU-bound):**

```yaml
requests: { memory: "512Mi", cpu: "500m" }
limits:   { memory: "2Gi",   cpu: "2000m" }
```

Der Worker bekommt deutlich mehr CPU-Ressourcen, weil FFmpeg rechenintensiv ist und mehrere Cores nutzen kann. Der API Gateway ist hauptsächlich I/O-bound (File-Uploads, API-Calls) und braucht weniger CPU.

---

**Erstellt:** 19.04.2026  
**Nächstes Dokument:** [Challenges](../06-lessons-learned/challenges.md)