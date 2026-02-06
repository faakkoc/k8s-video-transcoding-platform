# Hands-On: Erste Schritte mit Kubernetes

**Datum:** 04.02.2025  
**Status:** Abgeschlossen

---

## Ziel dieser Session

Eine einfache Python-Webapplikation in Kubernetes deployen, um die grundlegenden Konzepte praktisch zu verstehen:
- Was ist ein Kubernetes-Cluster?
- Wie funktionieren Pods, Deployments und Services?
- Wie deployed man eine Anwendung in Kubernetes?

---

## 1. Kind (Kubernetes in Docker)

### Was ist Kind?

**Kind** = **K**ubernetes **in** **D**ocker

Kind erstellt einen kompletten Kubernetes-Cluster als Docker-Container auf deinem lokalen Rechner. Statt VMs (wie bei Minikube) nutzt Kind Container, was deutlich schneller und ressourcenschonender ist.

### Warum Kind für lokale Entwicklung?

| Kriterium | Kind | Minikube | Docker Desktop K8s |
|-----------|------|----------|-------------------|
| **Geschwindigkeit** | Sehr schnell | Langsam (VM) | Mittel |
| **Ressourcen** | Wenig | Viel (VM-Overhead) | Mittel |
| **Multi-Cluster** | Ja | Nein | Nein |
| **CI/CD geeignet** | Ja | Nein | Nein |
| **Reset-Zeit** | Sekunden | Minuten | Minuten |

### Kind-Cluster erstellen

```bash
# Cluster-Konfiguration (kind-config.yaml)
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: video-transcoding-dev
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 80
    hostPort: 8080
    protocol: TCP
- role: worker
- role: worker
```

**Was bedeutet diese Konfiguration?**

- **`name: video-transcoding-dev`**: Name des Clusters (wichtig wenn man mehrere Cluster hat)
- **`role: control-plane`**: Der "Master"-Node, der den Cluster verwaltet
  - Entscheidet wo Pods laufen
  - Speichert Cluster-State (etcd)
  - Führt API-Server aus (kubectl kommuniziert hiermit)
- **`role: worker`** (2x): Die "Arbeiter"-Nodes, auf denen unsere Anwendungen laufen
  - Führen die eigentlichen Container aus
  - Haben kubelet (kommuniziert mit Control-Plane)
  - Haben Container-Runtime (Docker/containerd)
- **`extraPortMappings`**: Mappt Port 80 im Cluster auf Port 8080 auf deinem PC
  - Ermöglicht Zugriff von außen (localhost:8080 → Cluster)

**Cluster erstellen:**
```bash
kind create cluster --config kind-config.yaml
```

**Was passiert intern?**
1. Kind erstellt 3 Docker-Container (1 control-plane, 2 worker)
2. In jedem Container läuft ein vollständiger Kubernetes-Node
3. Die Nodes verbinden sich und bilden einen Cluster
4. kubectl wird automatisch konfiguriert, um mit diesem Cluster zu sprechen

**Verifizieren:**
```bash
# Welche Cluster existieren?
kind get clusters

# Kubernetes-Nodes anzeigen
kubectl get nodes
# NAME                              STATUS   ROLES           AGE
# video-transcoding-dev-control-plane Ready    control-plane   1m
# video-transcoding-dev-worker        Ready    <none>          1m
# video-transcoding-dev-worker2       Ready    <none>          1m

# Docker-Container anzeigen (Kind-Nodes sind Container!)
docker ps | grep video-transcoding-dev
```

---

## 2. Container-Image erstellen

### Was ist ein Container-Image?

Ein **Container-Image** ist ein Paket, das alles enthält, was eine Anwendung zum Laufen braucht:
- Betriebssystem (minimal, z.B. Alpine Linux)
- Runtime (z.B. Python, Node.js, Java)
- Anwendungs-Code
- Dependencies (Libraries, Packages)
- Konfiguration

**Analogie:** Ein Container-Image ist wie eine Installations-DVD. Ein Container ist die laufende Installation.

### Dockerfile - Die "Bauanleitung"

```dockerfile
FROM python:3.11-slim          # Basis-Image mit Python
WORKDIR /app                   # Arbeitsverzeichnis im Container
COPY requirements.txt .        # Dependencies-Liste kopieren
RUN pip install -r requirements.txt  # Dependencies installieren
COPY app.py .                  # Anwendungs-Code kopieren
EXPOSE 5000                    # Port dokumentieren (informativ)
CMD ["python", "app.py"]       # Startbefehl
```

**Schicht für Schicht (Layers):**
Docker baut Images in Schichten (Layers). Jede `RUN`, `COPY`, `ADD` Anweisung erstellt eine neue Schicht.

**Warum Schichten?**
- **Caching**: Unveränderte Schichten werden wiederverwendet
- **Effizienz**: Nur geänderte Schichten müssen neu gebaut werden
- **Sharing**: Mehrere Images können die gleiche Basis-Schicht teilen

**Best Practice aus unserem Dockerfile:**
```dockerfile
COPY requirements.txt .        # Erst Dependencies
RUN pip install -r requirements.txt
COPY app.py .                  # Dann Code
```

**Warum diese Reihenfolge?**
- Dependencies ändern sich selten → Layer wird gecacht
- Code ändert sich oft → nur dieser Layer wird neu gebaut
- Schnelleres Rebuild beim Entwickeln

### Image bauen

```bash
docker build -t test-app:v1 .
```

**Was bedeutet `-t test-app:v1`?**
- `-t` = Tag (Name + Version)
- `test-app` = Image-Name
- `v1` = Version-Tag (könnte auch `latest`, `1.0.0`, `dev` sein)

### Image in Kind-Cluster laden

**Problem:** Kind-Cluster ist isoliert. Er sieht deine lokalen Docker-Images nicht automatisch.

**Lösung:** Image explizit in den Cluster laden:
```bash
kind load docker-image test-app:v1 --name video-transcoding-dev
```

**Was passiert hier?**
1. Kind liest das Image aus deinem lokalen Docker
2. Kopiert es in **jeden Node** des Clusters
3. Speichert es in der Node-internen Container-Registry (containerd)

**Wichtig:** Nach jedem Docker Desktop Neustart müssen Images neu geladen werden!

---

## 3. Kubernetes Deployment

### Was ist ein Deployment?

Ein **Deployment** ist eine **Beschreibung des gewünschten Zustands** deiner Anwendung:
- Wie viele Instanzen (Replicas) sollen laufen?
- Welches Container-Image?
- Welche Resource-Limits?
- Welche Update-Strategie?

Kubernetes liest diese Beschreibung und sorgt **automatisch** dafür, dass dieser Zustand erreicht und gehalten wird.

### Deployment vs. Pod - Was ist der Unterschied?

| Konzept | Was ist es? | Beispiel |
|---------|-------------|----------|
| **Pod** | Kleinste Einheit, 1+ Container | Ein einzelner Container mit deiner App |
| **Deployment** | Management-Layer über Pods | "Ich will 3 Pods mit diesem Image" |

**Warum nicht direkt Pods erstellen?**
- Pods sind **ephemeral** (vergänglich)
- Wenn ein Pod stirbt, ist er weg
- Deployment erstellt automatisch neue Pods
- Deployment verwaltet Updates (Rolling, Rollback)

### Deployment YAML Schritt für Schritt

```yaml
apiVersion: apps/v1              # API-Version für Deployments
kind: Deployment                 # Typ der Ressource
metadata:
  name: test-app                 # Name des Deployments
  labels:
    app: test-app                # Labels für Organisieren/Filtern
```

**Metadata & Labels:**
- `name`: Eindeutiger Name in diesem Namespace
- `labels`: Key-Value Pairs zum Kategorisieren
  - Werden von Services genutzt um Pods zu finden
  - Können mit `kubectl get pods -l app=test-app` gefiltert werden

```yaml
spec:                            # Spezifikation des gewünschten Zustands
  replicas: 3                    # Anzahl der Pods
```

**Replicas:**
- `replicas: 3` = Kubernetes stellt sicher, dass **immer** 3 Pods laufen
- Stirbt ein Pod → neuer wird automatisch erstellt
- Kann mit `kubectl scale` geändert werden

```yaml
  selector:                      # Wie findet Deployment seine Pods?
    matchLabels:
      app: test-app              # Pods mit diesem Label gehören zu diesem Deployment
```

**Selector:**
- Verbindet Deployment mit Pods
- Deployment managed nur Pods mit passenden Labels
- Wichtig: Label im `selector` muss mit Label im `template` übereinstimmen

```yaml
  template:                      # Template für die Pods
    metadata:
      labels:
        app: test-app            # Label das auf Pods gesetzt wird
    spec:                        # Pod-Spezifikation
      containers:
      - name: test-app           # Container-Name (im Pod)
        image: test-app:v2       # Docker Image
        imagePullPolicy: IfNotPresent  # Image-Pull-Strategie
```

**ImagePullPolicy - Wichtig für Kind:**

| Policy | Bedeutung | Wann nutzen? |
|--------|-----------|--------------|
| `Always` | Immer von Registry pullen | Production mit Remote Registry |
| `IfNotPresent` | Nur pullen wenn lokal nicht vorhanden | Kind mit geladenen Images |
| `Never` | Nie pullen, nur lokal nutzen | Kind, muss existieren |

**Warum `IfNotPresent` für Kind?**
- Kind hat keine Remote-Registry
- Images werden mit `kind load` lokal geladen
- `IfNotPresent`: Nutzt lokales Image wenn vorhanden
- `Never`: Fehler wenn Image nicht geladen wurde

```yaml
        ports:
        - containerPort: 5000    # Port auf dem Container lauscht
```

**Ports:**
- Dokumentiert welcher Port intern genutzt wird
- Ermöglicht Kubernetes das Routing zu konfigurieren
- Ist **nicht** der Port nach außen (das macht der Service)

```yaml
        env:
        - name: APP_VERSION      # Environment Variable im Container
          value: "v2"
```

**Environment Variables:**
- Werden im Container als normale ENV vars gesetzt
- Python: `os.getenv('APP_VERSION')`
- Überschreiben Defaults im Code

```yaml
        resources:
          requests:                # Minimum-Garantie
            memory: "64Mi"
            cpu: "100m"
          limits:                  # Maximum-Grenze
            memory: "128Mi"
            cpu: "200m"
```

**Resources - Requests vs. Limits:**

- **Requests**: "Ich brauche mindestens..."
  - Kubernetes scheduled Pod nur auf Nodes mit genug freien Resources
  - `100m` = 0.1 CPU Cores (1000m = 1 Core)
  - `64Mi` = 64 Mebibyte RAM

- **Limits**: "Ich darf maximal..."
  - Container wird gedrosselt wenn er Limit erreicht
  - Bei Memory-Überschreitung: Pod wird killed (OOMKilled)

**Warum beides?**
- Verhindert "Noisy Neighbors" (ein Container frisst alle Resources)
- Ermöglicht effiziente Bin-Packing (mehrere Pods auf einem Node)

```yaml
        livenessProbe:           # Ist der Container noch am Leben?
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 10
```

**Liveness Probe:**
- Kubernetes fragt regelmäßig: "Lebst du noch?"
- HTTP GET auf `/health` alle 10 Sekunden
- Wenn fehlschlägt → Container wird neu gestartet
- `initialDelaySeconds: 5` = Warte 5 Sek nach Start bevor du prüfst

```yaml
        readinessProbe:          # Ist der Container bereit Traffic zu empfangen?
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 3
          periodSeconds: 5
```

**Readiness Probe:**
- Kubernetes fragt: "Bist du bereit?"
- Wenn fehlschlägt → Pod bekommt **keinen Traffic** (aus Service entfernt)
- Wichtig bei langsam startenden Apps
- Unterschied zu Liveness: Nicht neustarten, nur kein Traffic

**Liveness vs. Readiness:**
```
Start → [Ready Probe fails] → Pod bekommt keinen Traffic
     → [Ready Probe succeeds] → Pod bekommt Traffic
     → [Liveness Probe fails] → Pod wird neugestartet
```

### Deployment anwenden

```bash
kubectl apply -f deployment.yaml
```

**Was passiert?**
1. kubectl sendet YAML an Kubernetes API-Server
2. API-Server validiert und speichert in etcd (Cluster-Datenbank)
3. Deployment-Controller sieht: "3 Replicas gewünscht, 0 vorhanden"
4. Erstellt 3 Pods
5. Scheduler verteilt Pods auf Worker-Nodes
6. kubelet auf jedem Node startet die Container
7. Liveness/Readiness Probes beginnen

**Status prüfen:**
```bash
kubectl get deployments
# NAME       READY   UP-TO-DATE   AVAILABLE   AGE
# test-app   3/3     3            3           1m

# READY: 3/3 = 3 von 3 gewünschten Pods sind ready
# UP-TO-DATE: 3 = 3 Pods haben die aktuelle Version
# AVAILABLE: 3 = 3 Pods sind bereit Traffic zu empfangen

kubectl get pods
# NAME                        READY   STATUS    RESTARTS   AGE
# test-app-xxxxx-aaaaa        1/1     Running   0          1m
# test-app-xxxxx-bbbbb        1/1     Running   0          1m
# test-app-xxxxx-ccccc        1/1     Running   0          1m
```

---

## 4. Kubernetes Service

### Was ist ein Service?

Ein **Service** ist ein **stabiler Netzwerk-Endpunkt** für eine Gruppe von Pods.

**Problem ohne Service:**
- Pods haben dynamische IPs
- Pod stirbt → neue IP
- Wie erreiche ich meine App zuverlässig?

**Lösung mit Service:**
- Service hat eine **feste ClusterIP**
- Service hat einen **DNS-Namen** (z.B. `test-app-service`)
- Service leitet Traffic an alle passenden Pods weiter (**Load Balancing**)

### Service-Typen

| Typ | Zweck | Erreichbar von |
|-----|-------|----------------|
| **ClusterIP** | Interner Zugriff | Nur innerhalb des Clusters |
| **NodePort** | Externer Zugriff über Node-IP | Außerhalb (NodeIP:Port) |
| **LoadBalancer** | Cloud Load Balancer | Außerhalb (Cloud-Provider) |
| **ExternalName** | DNS-Alias | Überall (DNS-Weiterleitung) |

**Für lokale Entwicklung:** ClusterIP + Port-Forward (oder Ingress)

### Service YAML

```yaml
apiVersion: v1
kind: Service
metadata:
  name: test-app-service
spec:
  selector:
    app: test-app              # Alle Pods mit diesem Label
  ports:
  - port: 80                   # Port des Services (intern im Cluster)
    targetPort: 5000           # Port des Containers
  type: ClusterIP
```

**Wie funktioniert das Routing?**

```
Client (im Cluster)
    │
    ├─ Zugriff auf: test-app-service:80
    │
    ▼
Service (ClusterIP: 10.96.87.61)
    │
    ├─ Load Balancing (Round-Robin)
    │
    ├──▶ Pod 1 (10.244.1.7:5000)
    ├──▶ Pod 2 (10.244.2.9:5000)
    └──▶ Pod 3 (10.244.2.10:5000)
```

**Service Discovery:**
```bash
# Von einem anderen Pod im Cluster:
curl http://test-app-service:80

# Kubernetes DNS löst auf: 10.96.87.61
# Service leitet weiter an einen der 3 Pods
```

### Port-Forward für lokalen Zugriff

```bash
kubectl port-forward service/test-app-service 8080:80
```

**Was macht Port-Forward?**
```
Dein Browser (localhost:8080)
    │
    ├─ Port-Forward Tunnel
    │
    ▼
Service im Cluster (:80)
    │
    └─▶ Pod (zufällig ausgewählt)
```

**Wichtig:** Port-Forward ist **nur für Development**. Production nutzt Ingress oder LoadBalancer.

---

## 5. Rolling Update

### Was ist ein Rolling Update?

Ein **Rolling Update** ersetzt Pods schrittweise, ohne Downtime:

```
Vorher:  [Pod v1] [Pod v1] [Pod v1]
         ↓
Schritt 1: [Pod v1] [Pod v1] [Pod v2] (neue Version startet)
         ↓
Schritt 2: [Pod v1] [Pod v2] [Pod v2] (alte Version stirbt)
         ↓
Nachher:  [Pod v2] [Pod v2] [Pod v2]
```

**Vorteile:**
- Keine Downtime
- Bei Fehler: Automatisches Rollback möglich
- Graduelles Ausrollen (zuerst 1 Pod, dann Rest)

### Update durchführen

```bash
# Neue Version bauen
docker build -t test-app:v2 .

# In Kind laden
kind load docker-image test-app:v2 --name video-transcoding-dev

# Deployment updaten
kubectl set image deployment/test-app test-app=test-app:v2

# Oder deployment.yaml ändern und:
kubectl apply -f deployment.yaml
```

**Was passiert intern?**
1. Deployment erstellt **neue ReplicaSet** mit v2
2. Startet 1 neuen Pod (v2)
3. Wartet bis Readiness Probe succeeds
4. Stoppt 1 alten Pod (v1)
5. Wiederholt Schritte 2-4 bis alle Pods v2 sind

**Rollout beobachten:**
```bash
kubectl rollout status deployment/test-app
# Waiting for deployment "test-app" rollout to finish: 1 out of 3 new replicas have been updated...
# Waiting for deployment "test-app" rollout to finish: 2 out of 3 new replicas have been updated...
# deployment "test-app" successfully rolled out
```

### Rollback bei Problemen

```bash
# Letzte funktionierende Version wiederherstellen
kubectl rollout undo deployment/test-app

# Zu spezifischer Revision
kubectl rollout history deployment/test-app
kubectl rollout undo deployment/test-app --to-revision=2
```

---

## 6. Gelöste Probleme & Learnings

### Problem 1: ErrImageNeverPull

**Symptom:**
```
Status: ErrImageNeverPull
Message: Container image "test-app:v2" is not present with pull policy of Never
```

**Ursache:**
- Image wurde nicht in Kind-Cluster geladen
- Oder Docker Desktop war nicht gestartet

**Lösung:**
```bash
kind load docker-image test-app:v2 --name video-transcoding-dev
kubectl delete pods -l app=test-app  # Pods neu starten
```

**Learning:** Bei jedem Docker Desktop Neustart müssen Images neu geladen werden!

### Problem 2: Falsche Version wird angezeigt

**Symptom:** Browser zeigt v1 obwohl Deployment auf v2 steht

**Mögliche Ursachen:**

1. **Image nicht neu gebaut:**
```bash
# Altes Image löschen, neu bauen
docker rmi test-app:v2
docker build -t test-app:v2 .
```

2. **Image nicht in Cluster geladen:**
```bash
kind load docker-image test-app:v2 --name video-transcoding-dev
```

3. **Deployment referenziert alte Version:**
```bash
# Prüfen
kubectl get deployment test-app -o yaml | grep image:

# Fix
kubectl set image deployment/test-app test-app=test-app:v2
```

4. **ENV Variable überschreibt Default:**
```yaml
# Im Deployment:
env:
- name: APP_VERSION
  value: "v1"  # <-- Überschreibt den Default im Code!
```

**Learning:** 
- ENV Variables haben Vorrang vor Code-Defaults
- Immer `kubectl describe pod` nutzen um zu sehen was wirklich läuft

### Problem 3: Docker Desktop muss laufen

**Symptom:** Alle kubectl-Befehle schlagen fehl

**Ursache:** Kind-Cluster läuft als Docker-Container

**Lösung:** Docker Desktop starten, dann:
```bash
docker ps | grep video-transcoding-dev  # Cluster läuft wieder
kubectl get nodes                        # Funktioniert
```

---

## 7. Wichtige kubectl Commands

### Cluster & Nodes
```bash
# Cluster-Info
kubectl cluster-info

# Nodes anzeigen
kubectl get nodes

# Node-Details
kubectl describe node <NODE_NAME>
```

### Deployments
```bash
# Alle Deployments
kubectl get deployments

# Deployment-Details
kubectl describe deployment <NAME>

# Deployment skalieren
kubectl scale deployment <NAME> --replicas=5

# Deployment löschen
kubectl delete deployment <NAME>
```

### Pods
```bash
# Alle Pods
kubectl get pods

# Pods mit Details (IP, Node)
kubectl get pods -o wide

# Pods filtern nach Label
kubectl get pods -l app=test-app

# Pod-Details
kubectl describe pod <POD_NAME>

# Pod-Logs
kubectl logs <POD_NAME>
kubectl logs -f <POD_NAME>  # Follow

# In Pod reingehen (Shell)
kubectl exec -it <POD_NAME> -- /bin/sh

# Pod löschen
kubectl delete pod <POD_NAME>
```

### Services
```bash
# Alle Services
kubectl get services

# Service-Details
kubectl describe service <NAME>

# Port-Forward
kubectl port-forward service/<NAME> 8080:80
```

### Debugging
```bash
# Events anzeigen (was ist passiert?)
kubectl get events --sort-by='.lastTimestamp'

# Alle Ressourcen in einem Namespace
kubectl get all

# YAML einer Ressource anschauen
kubectl get deployment <NAME> -o yaml

# Rollout-Status
kubectl rollout status deployment/<NAME>

# Rollout-History
kubectl rollout history deployment/<NAME>
```

---

## 8. Zusammenfassung

### Was wir erreicht haben

✅ **Lokalen Kubernetes-Cluster** mit Kind erstellt (3 Nodes)
✅ **Container-Image** gebaut und verstanden (Dockerfile, Layers)
✅ **Kubernetes Deployment** erstellt und verstanden (Replicas, Probes, Resources)
✅ **Kubernetes Service** für Load Balancing konfiguriert
✅ **Rolling Update** durchgeführt (v1 → v2, zero downtime)
✅ **Debugging-Skills** entwickelt (Logs, Describe, Events)

### Schlüsselkonzepte verstanden

| Konzept | Zweck | Wichtig weil... |
|---------|-------|-----------------|
| **Pod** | Kleinste Einheit, 1+ Container | Grundbaustein von Kubernetes |
| **Deployment** | Managed Pods, Updates, Scaling | Production-ready Management |
| **Service** | Stabiler Netzwerk-Endpunkt | Load Balancing & Service Discovery |
| **Label & Selector** | Gruppierung & Filtering | Services finden ihre Pods |
| **Probe** | Health Checks | Self-Healing & Zero-Downtime |
| **Rolling Update** | Graduelle Updates | Keine Downtime bei Deployments |

### Nächste Schritte

Für die Video Transcoding Platform nutzen wir diese Konzepte:
- **API Gateway**: Deployment mit Service (ähnlich wie test-app)
- **Transcoding Worker**: Kubernetes **Jobs** statt Deployment (einmalige Tasks)
- **Message Queue**: StatefulSet für RabbitMQ/Redis (persistent state)
- **Storage**: PersistentVolumeClaims für Video-Files

---

**Erstellt:** 04.02.2025  
**Dauer:** ~3h (inkl. Debugging)  
