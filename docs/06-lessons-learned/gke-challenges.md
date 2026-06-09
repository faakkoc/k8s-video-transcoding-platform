# GKE Deployment: Challenges & Lessons Learned

**Datum:** 21.04.2026
**Aktualisiert:** 10.06.2026 — Signed URL Challenge ergänzt
**Status:** Abgeschlossen

---

## Übersicht

Das GKE Deployment verlief nicht ohne Hürden. Dieses Dokument protokolliert alle aufgetretenen Probleme chronologisch mit Root Cause Analysis und Fix.

> **Hinweis:** Die Challenges 2–4 (Namespace-Reihenfolge, Secret-Key-Namen, hardcoded S3-Config) entstanden alle durch den initialen HMAC-Key-Ansatz. Diese Probleme führten letztlich zur Architekturentscheidung, von HMAC Keys auf Workload Identity + native `google-cloud-storage` Library umzustellen. Der finale Deployment-Stand kennt kein `gcs-hmac-credentials` Secret mehr.

---

## Challenge 1: Hardcoded Bucket-Namen im Upload-Router

**Symptom:** `POST /api/v1/upload` → HTTP 500 `AccessDenied when calling PutObject`

**Ursache:**

```python
INPUT_BUCKET = os.getenv("INPUT_BUCKET", "uploads")  # ← ENV korrekt definiert

# Aber im Upload-Handler:
success = s3_client.upload_file(
    bucket="uploads",  # ← HARDCODED — ignoriert ENV-Variable
    key=input_key
)
```

**Fix:**
```python
success = s3_client.upload_file(
    bucket=INPUT_BUCKET,  # ← ENV-Variable genutzt
    key=input_key
)
```

**Learning:** Eine ENV-Variable zu definieren reicht nicht — sie muss auch tatsächlich verwendet werden.

---

## Challenge 2: Namespace/Secret Reihenfolge (HMAC-Phase)

> **Kontext:** Diese Challenge betrifft den initialen HMAC-Ansatz bei dem Terraform ein Kubernetes Secret erstellt hat. Im aktuellen Stand (Workload Identity) existiert dieses Secret nicht mehr.

**Symptom:** Nach `terraform apply` fehlte das Secret `gcs-hmac-credentials` im Cluster.

**Ursache:** Terraform erstellte das Kubernetes Secret über den Kubernetes Provider direkt während `terraform apply`. Wenn der Namespace noch nicht existierte, schlug die Secret-Erstellung fehl.

**Heutige Lösung:** Der Namespace wird in der CI/CD Pipeline vor `terraform apply` erstellt. Das Secret existiert nicht mehr — Workload Identity ersetzt es vollständig.

**Learning:** Abhängigkeiten zwischen Terraform und Kubernetes müssen explizit sein.

---

## Challenge 3: Falsche Secret-Key-Namen (HMAC-Phase)

> **Kontext:** Betrifft den initialen HMAC-Ansatz.

**Symptom:** `CreateContainerConfigError` — Pods starten nicht.

```
Error: couldn't find key api-gateway-access-key in Secret gcs-hmac-credentials
```

**Heutige Relevanz:** Mit Workload Identity gibt es kein `gcs-hmac-credentials` Secret mehr. Diese Challenge ist damit obsolet — dokumentiert als Motivation für den Architektur-Wechsel.

---

## Challenge 4: Hardcoded Worker S3-Konfiguration

**Symptom:** Worker verbindet sich zu `http://minio:9000` statt GCS.

**Ursache:** `k8s_client.py` hatte die S3-Konfiguration für Worker-Jobs hardcoded.

**Fix:** API Gateway liest seine eigene Konfiguration und gibt sie an den Worker weiter. Mit Workload Identity vereinfacht sich das: nur `STORAGE_PROVIDER=gcs` muss übergeben werden, keine Credentials.

**Learning:** Bei dynamisch erstellten Jobs muss die Konfigurationsweitergabe explizit implementiert werden.

---

## Challenge 5: Worker Image nicht in Artifact Registry

**Symptom:** `ImagePullBackOff` beim Worker-Pod.

**Ursache:** `k8s_client.py` hatte `transcoding-worker:latest` hardcoded ohne Registry-Prefix.

**Fix:** Image aus ENV-Variable (`TRANSCODING_WORKER_IMAGE`) lesen, die aus der ConfigMap befüllt wird:
```yaml
worker_image: "us-east1-docker.pkg.dev/k8s-transcoding-plattform/transcoding/transcoding-worker:latest"
```

---

## Challenge 6: Artifact Registry nach terraform destroy leer

**Symptom:** Nach `terraform destroy` und erneutem `apply` → `ImagePullBackOff`.

**Fix:** `prevent_destroy = true` auf der Artifact Registry Ressource. Die CI/CD Pipeline pusht Images automatisch bei jedem Commit auf `main`.

**Learning:** Die Artifact Registry ist dauerhafte Infrastruktur — `terraform destroy` sollte sie nicht löschen.

---

## Challenge 7: GKE Autopilot Scale-Up-Fehler

**Symptom:** Worker-Pod bleibt `Pending`, Event: `GCE quota exceeded`.

**Ursache:** Zonen-spezifische GCE Quota. Nach kurzer Wartezeit wählt der Scheduler automatisch eine andere Zone.

**Kein expliziter Fix nötig** — der Cluster erholt sich selbst.

---

## Challenge 8: GKE Zonen-Konflikt (`us-central1` → `us-east1`)

**Symptom:**
```
Error: Cluster location change not allowed.
Current locations [us-central1-a us-central1-b us-central1-c],
new locations [us-central1-a us-central1-b us-central1-c us-central1-f]
```

**Ursache:** Das GKE Terraform Modul nutzt `random_shuffle` für Zonen-Auswahl. GCP fügte Zone `us-central1-f` hinzu — beim nächsten Plan erkannte Terraform eine Änderung und versuchte den Cluster zu modifizieren, was GKE ablehnt.

**Fix:** Region auf `us-east1` gewechselt. `us-east1` hat ein stabileres Zonen-Set (`b`, `c`, `d`) und löst dieses Problem nicht aus.

---

## Challenge 9: Signed URLs mit Workload Identity

**Symptom:** `GET /api/v1/download/{job_id}` → HTTP 500 `Failed to generate download URL`

**Fehlermeldung in den Logs:**
```
you need a private key to sign credentials. the credentials you are currently using
<class 'google.auth.compute_engine.credentials.Credentials'> just contains a token.
```

**Ursache:** `generate_signed_url()` der `google-cloud-storage` Library erwartet standardmäßig einen Private Key zum Signieren der URL. Workload Identity stellt jedoch nur ein kurzlebiges OAuth2-Token bereit — keinen Private Key.

**Fehlgeschlagener Fix-Versuch:** `roles/iam.serviceAccountTokenCreator` IAM Binding hinzufügen — allein nicht ausreichend.

**Korrekter Fix:** Die `generate_signed_url()` Methode unterstützt alternativ `service_account_email` + `access_token` statt eines Private Keys. Das Token wird über die Credentials API abgerufen:

```python
import google.auth
import google.auth.transport.requests

credentials, _ = google.auth.default()
credentials.refresh(google.auth.transport.requests.Request())

url = blob.generate_signed_url(
    expiration=timedelta(seconds=expiration),
    method="GET",
    version="v4",
    service_account_email=credentials.service_account_email,
    access_token=credentials.token,
)
```

**Learning:** Workload Identity ist nicht vollständig transparent — Operationen die einen Private Key erfordern (wie URL-Signing) brauchen eine spezifische Implementierung. Die Fehlermeldung der Library ist zwar klar, aber der Fix ist nicht offensichtlich dokumentiert.

---

## Trade-off: Transcoding-Latenz vs. Kosten bei GKE Autopilot

**Beobachtung:** 3–5 Minuten vom Upload bis zum abgeschlossenen Job — obwohl FFmpeg nur ~9 Sekunden benötigt.

**Ursache:** GKE Autopilot Scale-Up wenn kein Node verfügbar:

```
Upload → Job erstellt → Pod Pending
    → Autopilot: kein Node verfügbar
    → Neuen Node provisionieren (~60–90s)
    → Image aus Artifact Registry pullen (~30s)
    → FFmpeg Transcoding (~9s)
    → Upload Output zu GCS (~2s)
    → Job Completed
```

**Warum Autopilot trotzdem?** Kostenkontrolle: Nodes laufen nur wenn Jobs aktiv sind. Für ein PoC-Projekt ist der Trade-off akzeptabel. Ein produktiver Einsatz würde Standard GKE mit vorprovisioniertem Node Pool nutzen.

---

## Zusammenfassung: Root Causes

| Challenge | Root Cause | Status |
|-----------|------------|--------|
| Hardcoded Bucket-Namen | ENV-Variable definiert aber nicht genutzt | ✅ Behoben |
| Namespace/Secret Reihenfolge | HMAC-Phase — Abhängigkeit Terraform/K8s | ✅ Obsolet (Workload Identity) |
| Falsche Secret-Key-Namen | HMAC-Phase — Inkonsistenz Secret/Deployment | ✅ Obsolet (Workload Identity) |
| Hardcoded Worker S3-Config | Konfigurationsweitergabe fehlte | ✅ Behoben |
| Hardcoded Worker Image | Keine ENV-Variable für Registry-Pfad | ✅ Behoben |
| Leere Artifact Registry | terraform destroy ohne prevent_destroy | ✅ Behoben |
| Autopilot Scale-Up | Zonen-Quota temporär | ✅ Selbst erholt |
| Zonen-Konflikt us-central1 | random_shuffle + neue GCP-Zone | ✅ us-east1 genutzt |
| Signed URLs mit Workload Identity | Private Key erwartet, Token vorhanden | ✅ IAM Credentials API genutzt |