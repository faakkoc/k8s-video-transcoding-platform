# Deployment Success - API Gateway

**Datum:** 08.02.2026  
**Status:** ✅ Erfolgreich deployed

---

## Was wurde deployed?

### Services
- **API Gateway** (FastAPI)
    - 2 Replicas
    - Health Checks aktiv
    - RBAC konfiguriert

### Kubernetes Ressourcen
- Namespace: `video-transcoding`
- Deployment: `api-gateway` (2 Pods)
- Service: `api-gateway` (ClusterIP)
- ServiceAccount: `api-gateway` (mit Job-Erstellung Rechten)
- HPA: `api-gateway-hpa` (2-10 Replicas)

---

## Deployment-Prozess

### 1. Docker Image gebaut
```bash
cd ~/k8s-video-transcoding-platform/services/api-gateway
docker build -t api-gateway:latest .
```

**Warnung beim Build:**
```
FromAsCasing: 'as' and 'FROM' keywords' casing do not match (line 3)
```
→ Harmlos, kann später mit `FROM ... AS builder` gefixt werden

### 2. Image in Kind-Cluster geladen
```bash
kind load docker-image api-gateway:latest --name video-transcoding
```

**Wichtig:** Nach jedem Docker Desktop Neustart muss Image neu geladen werden!

### 3. Kubernetes Manifests angewendet
```bash
cd ~/k8s-video-transcoding-platform

# Reihenfolge wichtig!
kubectl apply -f kubernetes/local/api-gateway/service-account.yaml
kubectl apply -f kubernetes/local/api-gateway/deployment.yaml
kubectl apply -f kubernetes/local/api-gateway/service.yaml
kubectl apply -f kubernetes/local/api-gateway/hpa.yaml
```

### 4. Verifizierung
```bash
# Status prüfen
kubectl get all -n video-transcoding -l app=api-gateway

# Output:
NAME                              READY   STATUS    RESTARTS   AGE
pod/api-gateway-xxxxx-aaaaa       1/1     Running   0          5m
pod/api-gateway-xxxxx-bbbbb       1/1     Running   0          5m

NAME                  TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
service/api-gateway   ClusterIP   10.96.123.45    <none>        80/TCP    5m

NAME                          READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/api-gateway   2/2     2            2           5m
```

### 5. Zugriff via Port-Forward
```bash
kubectl port-forward -n video-transcoding svc/api-gateway 8080:80
```

**Browser:** http://localhost:8080/api/v1/docs

✅ Swagger UI erfolgreich geladen!

---

## Was funktioniert?

### Endpoints

| Method | Path | Status | Beschreibung |
|--------|------|--------|--------------|
| GET | `/` | ✅ | API Info |
| GET | `/api/v1/health` | ✅ | Liveness Probe |
| GET | `/api/v1/ready` | ✅ | Readiness Probe |
| GET | `/api/v1/docs` | ✅ | Swagger UI |

### Kubernetes Features

✅ **Rolling Updates**: maxSurge=1, maxUnavailable=0 konfiguriert  
✅ **Health Probes**: Liveness & Readiness aktiv  
✅ **RBAC**: ServiceAccount kann Jobs erstellen  
✅ **Resource Limits**: 128Mi-512Mi Memory, 100m-500m CPU  
✅ **HPA**: Auto-Scaling bei 70% CPU konfiguriert

---

## Learnings

### Was gut lief

✅ **Multi-Stage Dockerfile** - Image nur ~200MB statt >1GB  
✅ **Kind-Cluster Setup** - Schnell, reproduzierbar  
✅ **Dokumentation parallel** - Kein Wissen verloren  
✅ **Git-Struktur** - Saubere Trennung Code/Docs

### Herausforderungen

⚠️ **Line-Ending Warning** - Windows/Linux Unterschiede  
→ Gelöst mit `git config --global core.autocrlf true`

⚠️ **Docker Desktop muss laufen** - Cluster startet nicht ohne  
→ Immer zuerst `docker ps` prüfen

⚠️ **Images müssen in Kind geladen werden** - Nicht automatisch verfügbar  
→ `kind load docker-image` nach jedem Build

### Debugging-Tools genutzt

- `kubectl describe pod` - Detaillierte Pod-Info
- `kubectl logs` - Container-Logs
- `kubectl get events` - Cluster-Events
- **k9s** - Visuelles Cluster-Management (sehr hilfreich!)

---

## Nächste Schritte

### Phase 2: Upload Endpoint

**Feature Branch:** `feature/upload-endpoint`

1. Upload Router implementieren (`app/routers/upload.py`)
2. File-Validierung (Format, Größe)
3. Kubernetes Job Template
4. Job-Erstellung aus API
5. Testing mit echter Video-Datei

**Geschätzte Dauer:** 2-3 Stunden

### Phase 3: Transcoding Worker

1. FFmpeg-Container erstellen
2. Worker-Script (Python + FFmpeg)
3. Input/Output Handling
4. Kubernetes Job Integration

### Phase 4: Storage

1. MinIO deployment (S3-kompatibel)
2. PersistentVolumeClaims
3. Migration von emptyDir zu Object Storage

---

## Screenshots

*(Hier könnten Screenshots eingefügt werden)*

- [ ] Swagger UI
- [ ] k9s Pod-Ansicht
- [ ] kubectl get all Output

---

**Erstellt:** 08.02.2026  
**Nächstes Update:** Nach Upload-Feature Implementation