# GKE Deployment: Challenges & Lessons Learned

**Datum:** 21.04.2026
**Status:** Abgeschlossen

---

## Übersicht

Das GKE Deployment verlief nicht ohne Hürden. Dieses Dokument protokolliert alle aufgetretenen Probleme chronologisch mit Root Cause Analysis und Fix — analog zu den lokalen Challenges aus dem Kind-Deployment.

---

## Challenge 1: Hardcoded Bucket-Namen im Upload-Router

**Symptom:** `POST /api/v1/upload` → HTTP 500 `AccessDenied when calling PutObject`

**Zeitaufwand:** ~1 Stunde Debugging

**Analyse:**

Der Fehler war irreführend. Direkte boto3-Tests im Pod funktionierten einwandfrei:

```python
# Im Pod-Terminal: funktioniert
client.upload_fileobj(BytesIO(b'test'), 'k8s-transcoding-uploads', 'test.txt')
# OK
```

Aber der Upload-Endpoint lieferte `AccessDenied`. Nach systematischem Durchsuchen des Codes wurde die Ursache gefunden:

```python
# services/api-gateway/app/routers/upload.py
INPUT_BUCKET = os.getenv("INPUT_BUCKET", "uploads")  # ← ENV korrekt definiert

# Aber im Upload-Handler:
success = s3_client.upload_file(
    file_obj=file_obj,
    bucket="uploads",  # ← HARDCODED! Ignoriert die ENV-Variable
    key=input_key
)
```

Der GCS-Bucket heißt `k8s-transcoding-uploads`, nicht `uploads`. Der Code hat die richtige ENV-Variable definiert, sie aber nie genutzt.

**Fix:**

```python
success = s3_client.upload_file(
    file_obj=file_obj,
    bucket=INPUT_BUCKET,  # ← ENV-Variable genutzt
    key=input_key
)
```

**Learning:** Bei der Migration von lokaler zu Cloud-Umgebung müssen alle hardcodierten Werte geprüft werden. Eine ENV-Variable zu definieren reicht nicht — sie muss auch tatsächlich verwendet werden. Code-Reviews oder Linter-Regeln die auf hardcoded Strings prüfen, hätten dies früher aufgedeckt.

---

## Challenge 2: Namespace/Secret Reihenfolge

**Symptom:** Nach `terraform apply` fehlte das Secret `gcs-hmac-credentials` im Cluster.

**Analyse:**

Terraform erstellt das Kubernetes Secret über den Kubernetes Provider direkt während `terraform apply`. Wenn der Namespace `video-transcoding` zu diesem Zeitpunkt noch nicht existiert, scheitert die Secret-Erstellung — oder das Secret landet im falschen Namespace.

```
terraform apply
  → Secret erstellen in Namespace "video-transcoding"
  → Namespace existiert nicht
  → Secret geht verloren / Fehler
```

**Fix:**

Der Namespace muss **vor** `terraform apply` erstellt werden:

```fish
# Korrekte Reihenfolge:
kubectl apply -f kubernetes/gke/00-namespace.yaml  # 1. Namespace
terraform apply                                     # 2. Terraform (erstellt Secret)
kubectl apply -f kubernetes/gke/01-configmap.yaml  # 3. Rest der Manifests
kubectl apply -f kubernetes/gke/02-service-accounts.yaml
kubectl apply -f kubernetes/gke/api-gateway/
```

**Alternativer Fix (nicht implementiert):** Den Namespace direkt in Terraform als `kubernetes_namespace` Ressource definieren. Das würde die Abhängigkeit explizit machen und das Henne-Ei-Problem lösen.

**Learning:** Abhängigkeiten zwischen Terraform und Kubernetes müssen explizit sein. Implizite Annahmen über die Reihenfolge von Operationen führen zu schwer nachvollziehbaren Fehlern.

---

## Challenge 3: Falsche Secret-Key-Namen

**Symptom:** `CreateContainerConfigError` — Pods starten nicht.

**Fehlermeldung:**

```
Error: couldn't find key api-gateway-access-key in Secret video-transcoding/gcs-hmac-credentials
```

**Analyse:**

Das Secret wurde manuell erstellt mit den Key-Namen `access-key` und `secret-key`:

```fish
kubectl create secret generic gcs-hmac-credentials \
  --from-literal=access-key=GOOG1E...  # ← falscher Key-Name
  --from-literal=secret-key=...
```

Das Deployment erwartete aber andere Key-Namen gemäß `deployment.yaml`:

```yaml
secretKeyRef:
  name: gcs-hmac-credentials
  key: api-gateway-access-key  # ← erwartet
```

**Fix:**

Secret mit korrekten Key-Namen neu erstellen:

```fish
kubectl delete secret gcs-hmac-credentials -n video-transcoding

kubectl create secret generic gcs-hmac-credentials \
  --from-literal=api-gateway-access-key=$(terraform output -raw api_gateway_hmac_access_key) \
  --from-literal=api-gateway-secret=$(terraform output -raw api_gateway_hmac_secret) \
  --from-literal=worker-access-key=$(terraform output -raw worker_hmac_access_key) \
  --from-literal=worker-secret=$(terraform output -raw worker_hmac_secret) \
  -n video-transcoding
```

**Hinweis:** Dieser manuelle Schritt war nur notwendig weil das Secret beim ersten `terraform apply` verloren gegangen war (Challenge 2). Nach korrekter Namespace-Reihenfolge erstellt Terraform das Secret mit den richtigen Key-Namen automatisch.

**Learning:** Secret-Key-Namen müssen exakt mit den Referenzen im Deployment übereinstimmen. Kubernetes gibt bei falschen Key-Namen einen `CreateContainerConfigError` — die Fehlermeldung ist klar, aber das Debugging dauert trotzdem, weil der Fehler erst beim Pod-Start auftritt.

---

## Challenge 4: Hardcoded Worker S3-Konfiguration

**Symptom:** Worker-Pod startet, schlägt aber fehl mit:

```
[ERROR] Unexpected error during download:
Could not connect to the endpoint URL: "http://minio:9000/uploads/..."
```

**Analyse:**

`k8s_client.py` hat die S3-Konfiguration für Worker-Jobs hardcoded:

```python
env=[
    client.V1EnvVar(name="S3_ENDPOINT", value="http://minio:9000"),  # ← hardcoded
    client.V1EnvVar(name="S3_ACCESS_KEY", value="minioadmin"),        # ← hardcoded
    client.V1EnvVar(name="S3_SECRET_KEY", value="minioadmin123"),     # ← hardcoded
    client.V1EnvVar(name="INPUT_BUCKET",  value="uploads"),           # ← hardcoded
    client.V1EnvVar(name="OUTPUT_BUCKET", value="outputs"),           # ← hardcoded
]
```

Die Worker-Jobs erbten nicht die Konfiguration des API Gateways. Stattdessen bekamen sie die lokalen MinIO-Werte — obwohl der Cluster in GKE lief.

**Fix:**

Der API Gateway liest seine eigene ENV-Konfiguration und gibt sie an die Worker-Jobs weiter:

```python
env=[
    client.V1EnvVar(name="S3_ENDPOINT",   value=os.getenv("S3_ENDPOINT", "http://minio:9000")),
    client.V1EnvVar(name="S3_ACCESS_KEY",  value=os.getenv("WORKER_S3_ACCESS_KEY", "minioadmin")),
    client.V1EnvVar(name="S3_SECRET_KEY",  value=os.getenv("WORKER_S3_SECRET_KEY", "minioadmin123")),
    client.V1EnvVar(name="INPUT_BUCKET",   value=os.getenv("INPUT_BUCKET", "uploads")),
    client.V1EnvVar(name="OUTPUT_BUCKET",  value=os.getenv("OUTPUT_BUCKET", "outputs")),
]
```

Zusätzlich wurde im Deployment eine separate ENV-Variable für Worker-Credentials eingeführt (`WORKER_S3_ACCESS_KEY`, `WORKER_S3_SECRET_KEY`), da API Gateway und Worker unterschiedliche HMAC Keys haben.

**Learning:** Bei dynamisch erstellten Jobs (Jobs die andere Jobs starten) muss die Konfigurationsweitergabe explizit implementiert werden. Kubernetes Jobs erben keine ENV-Variablen vom erstellenden Pod — jede ENV-Variable muss explizit übergeben werden.

---

## Challenge 5: Worker Image nicht in Artifact Registry

**Symptom:** `ImagePullBackOff` beim Worker-Pod.

**Fehlermeldung:**

```
Failed to pull image "transcoding-worker:latest": not found
```

**Analyse:**

`k8s_client.py` hat das Worker-Image hardcoded als `transcoding-worker:latest` — den lokalen Image-Namen ohne Registry-Prefix. GKE versucht dieses Image von Docker Hub zu pullen, wo es nicht existiert.

```python
image="transcoding-worker:latest"  # ← lokal, nicht in Artifact Registry
```

**Fix:**

Image aus ENV-Variable lesen, die aus der ConfigMap befüllt wird:

```python
image=os.getenv("TRANSCODING_WORKER_IMAGE", "transcoding-worker:latest")
```

Im Deployment wird `TRANSCODING_WORKER_IMAGE` aus der ConfigMap gelesen:

```yaml
- name: TRANSCODING_WORKER_IMAGE
  valueFrom:
    configMapKeyRef:
      name: platform-config
      key: worker_image
```

In der ConfigMap steht der vollständige Artifact Registry Pfad:

```yaml
worker_image: "us-central1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/transcoding-worker:latest"
```

**Learning:** Image-Namen müssen umgebungsspezifisch konfigurierbar sein. Eine CI/CD Pipeline würde dieses Problem grundsätzlich lösen — sie würde das Image automatisch mit dem korrekten Registry-Prefix bauen und pushen, und den Image-Namen in der ConfigMap aktualisieren.

---

## Challenge 6: Artifact Registry nach terraform destroy leer

**Symptom:** Nach erneutem `terraform apply` → `ImagePullBackOff` für alle Pods.

**Analyse:**

`terraform destroy` löscht die Artifact Registry inklusive aller gepushten Images. Nach erneutem `terraform apply` ist die Registry leer — alle Pods scheitern mit `ImagePullBackOff`.

**Fix (manuell):** Nach jedem `terraform apply` müssen beide Images neu gebaut und gepusht werden:

```fish
docker build -t us-central1-docker.pkg.dev/.../api-gateway:latest services/api-gateway/
docker push us-central1-docker.pkg.dev/.../api-gateway:latest

docker build -t us-central1-docker.pkg.dev/.../transcoding-worker:latest services/transcoding-worker/
docker push us-central1-docker.pkg.dev/.../transcoding-worker:latest
```

**Langfristige Lösung:** Eine GitHub Actions CI/CD Pipeline baut und pusht Images automatisch nach jedem Commit auf den Main-Branch. Damit ist sichergestellt, dass die Artifact Registry immer aktuelle Images enthält — unabhängig davon ob die Infrastruktur neu aufgebaut wird.

Alternativ: `prevent_destroy = true` in der Artifact Registry Ressource verhindert das versehentliche Löschen durch `terraform destroy`.

**Learning:** `terraform destroy` ist in der Praxis eine Operation die man selten ausführt. Im Rahmen eines PoC-Projekts mit begrenztem GCP-Budget wurde `terraform destroy` nach jeder Session ausgeführt um Kosten zu sparen — was dieses Problem immer wieder reproduziert hat. Eine CI/CD Pipeline macht dieses Problem irrelevant.

---

## Challenge 7: GKE Autopilot Scale-Up-Fehler

**Symptom:** Worker-Pod bleibt `Pending` mit Event:

```
Node scale up in zones us-central1-b associated with this pod failed: GCE quota exceeded.
```

**Analyse:**

GKE Autopilot versucht, einen neuen Node in `us-central1-b` hochzufahren, scheitert aber an der GCE Quota. Die Quota-Prüfung über `gcloud compute regions describe` zeigt jedoch ausreichend freie Kapazität in der Region.

Das Problem war zonen-spezifisch: Autopilot wählte `us-central1-b`, aber die verfügbaren Quotas lagen in anderen Zonen. Nach einer kurzen Wartezeit wählte der Scheduler automatisch eine andere Zone (`us-central1-a`) und der Node-Start gelang.

**Fix:** Kein expliziter Fix erforderlich — der Cluster hat sich selbst erholt. Der Pod wurde nach ~2–3 Minuten erfolgreich scheduled.

**Learning:** GKE Autopilot Scale-Up ist nicht sofort. Bei Batch-Workloads (Transcoding Jobs) ist eine Wartezeit von 60–90 Sekunden für den ersten Job nach längerem Leerlauf normal und erwartet. Diese Latenz ist ein bekannter Trade-off von Autopilot gegenüber Standard GKE mit vorprovisioned Node Pools.

---

## Trade-off: Transcoding-Latenz vs. Kosten bei GKE Autopilot

**Beobachtung:** Der Zeitraum vom Video-Upload bis zum abgeschlossenen Transcoding-Job beträgt auf GKE Autopilot **3–5 Minuten**, obwohl FFmpeg das eigentliche Transcoding in unter 10 Sekunden erledigt. Der Großteil der Zeit entfällt auf den GKE Autopilot Scale-Up.

**Ursache:**

GKE Autopilot fährt Nodes nur bei Bedarf hoch und skaliert sie wieder herunter wenn keine Last vorhanden ist. Wenn ein Transcoding-Job erstellt wird und kein passender Node verfügbar ist, läuft folgender Prozess ab:

```
Upload → Job erstellt → Pod Pending
    → Autopilot erkennt: kein Node verfügbar
    → Neuen Node in GCE provisionieren (~60–90s)
    → Node startet, Container-Runtime initialisiert
    → Pod scheduled, Image aus Artifact Registry pullen (~30s)
    → FFmpeg Transcoding (~9s)
    → Upload Output zu GCS (~2s)
    → Job Completed
```

**Warum wurde Autopilot trotzdem gewählt?**

Für dieses PoC-Projekt überwiegen die Vorteile:

- **Kostenkontrolle:** Nodes laufen nur wenn tatsächlich Transcoding-Jobs aktiv sind. Ein 24/7 laufender Node würde für ein selten genutztes Demo-Projekt unnötige Kosten verursachen.
- **Kein Node-Management:** Kein manuelles Provisionieren von VM-Typen, Node-Pool-Konfiguration oder Patch-Management.
- **Automatische Skalierung:** Bei mehreren gleichzeitigen Jobs skaliert Autopilot automatisch hoch.

**Mögliche Optimierungen (nicht implementiert):**

Ein Standard GKE Cluster mit einem vorprovisionierten Node Pool würde die Latenz auf ~15 Sekunden reduzieren, da kein Scale-Up mehr nötig ist. Der Trade-off ist dann umgekehrt: konstante Kosten auch ohne Last.

Eine weitere Option wäre ein "Burst"-Ansatz: ein kleiner dauerhafter Node für den API Gateway und Autopilot nur für Worker-Jobs. Das würde die Latenz auf ~30–60 Sekunden reduzieren.

**Für den produktiven Einsatz** in einem echten Broadcast-Workflow wäre die Autopilot-Latenz nicht akzeptabel. Für ein wissenschaftliches PoC-Projekt ist sie vertretbar und liefert gleichzeitig ein konkretes Beispiel für den Kosteneinsparung-vs.-Latenz-Trade-off bei Cloud-nativen Architekturen.

---

## Zusammenfassung: Root Causes

| Challenge | Root Cause | Kategorie |
|-----------|------------|-----------|
| Hardcoded Bucket-Namen | Fehlende Nutzung definierter ENV-Vars | Code-Qualität |
| Namespace/Secret Reihenfolge | Implizite Abhängigkeit zwischen Terraform und K8s | Deployment-Prozess |
| Falsche Secret-Key-Namen | Inkonsistenz zwischen Secret und Deployment | Konfiguration |
| Hardcoded Worker S3-Config | Fehlende Konfigurationsweitergabe an Jobs | Architektur |
| Hardcoded Worker Image | Keine Umgebungskonfiguration für Images | Konfiguration |
| Leere Artifact Registry | Kein CI/CD, manuelle Infrastruktur-Zyklen | Prozess |
| Autopilot Scale-Up | Zonen-spezifische GCE Quota, temporär | Infrastruktur |

Die meisten Probleme haben eine gemeinsame Wurzel: Der Code wurde zunächst für die lokale Umgebung entwickelt mit hardcoded Werten (MinIO, Bucket-Namen, Image-Namen). Beim Cloud-Deployment wurden diese Werte nicht konsequent durch ENV-Variablen ersetzt.

**Generelles Learning:** Cloud-Agnostik ist kein Selbstläufer. Es reicht nicht, boto3 als S3-Abstraktion zu verwenden — auch alle Konfigurationswerte (Endpoints, Bucket-Namen, Image-Namen, Credentials) müssen von Anfang an über ENV-Variablen konfigurierbar sein. Hardcoded lokale Werte rächen sich spätestens beim ersten Cloud-Deployment.

---

**Vorheriges Dokument:** [Step-by-Step Deployment & E2E Test](./gke-e2e-test.md)