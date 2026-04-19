# Was gut funktioniert hat

**Datum:** 19.04.2026  
**Status:** Abgeschlossen

---

## Überblick

Neben den Herausforderungen gab es Aspekte der Entwicklung die überraschend gut funktioniert haben — teils durch bewusste Entscheidungen, teils durch die gewählten Technologien.

---

## 1. Schrittweise Implementierung statt Big Bang

Die Plattform wurde in klar abgegrenzten Phasen gebaut, wobei jede Phase einzeln getestet wurde bevor die nächste begann:

```
Phase 1: API Gateway deployen (Health Endpoints, RBAC)
    ↓
Phase 2: Upload Endpoint + File Validation
    ↓
Phase 3: Kubernetes Job Creation (ohne Worker)
    ↓
Phase 4: Transcoding Worker (mit bekanntem emptyDir-Problem)
    ↓
Phase 5: MinIO Integration (löst Storage-Problem)
    ↓
Phase 6: Job Status + Download Endpoints
```

**Warum das funktioniert hat:**

Jeder Schritt hatte einen klar definierten Erfolgscheck. Wenn Phase 3 fehlschlug, war das Debugging auf `k8s_client.py` und die RBAC-Konfiguration beschränkt — nicht auf das gesamte System. Ein "Big Bang"-Ansatz (alles auf einmal implementieren und dann debuggen) hätte bei einem komplexen verteilten System zu erheblich längeren Debugging-Sessionen geführt.

---

## 2. FastAPI Swagger UI als Development-Tool

Die automatisch generierte Swagger UI unter `/api/v1/docs` war während der gesamten Entwicklung das primäre Test-Interface:

- File-Uploads direkt im Browser ohne curl oder Postman
- Request/Response-Schemas sofort sichtbar
- Validierungsfehler direkt angezeigt
- Kein separates API-Client-Setup nötig

**Konkret:** Jeder Upload-Test, jede Job-Status-Abfrage und jeder Download-Test wurde über die Swagger UI durchgeführt. Das spart Zeit und reduziert Fehlerquellen durch manuelle curl-Befehle.

---

## 3. boto3 S3-API als Abstraktionsschicht

Die Entscheidung, boto3 mit der S3-kompatiblen API zu verwenden, hat sich als richtig erwiesen. Derselbe Code läuft gegen MinIO (lokal) und wird gegen Google Cloud Storage und StackIT Object Storage laufen — ohne Code-Änderungen:

```python
# Dieser Code ist identisch für alle drei Backends:
s3_client = boto3.client(
    's3',
    endpoint_url=os.getenv("S3_ENDPOINT"),
    aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
)

s3_client.upload_fileobj(file_obj, bucket, key)
s3_client.download_file(bucket, key, local_path)
s3_client.generate_presigned_url('get_object', ...)
```

Der Wechsel zwischen Umgebungen passiert ausschließlich über ENV-Variablen in den Kubernetes-Manifests — der Anwendungscode bleibt unverändert. Das ist Cloud-Agnostik in der Praxis.

---

## 4. Kubernetes Health Probes für automatisches Self-Healing

Liveness und Readiness Probes haben mehrfach automatisch eingegriffen ohne manuelles Eingreifen:

- Pods die beim Start fehlschlugen wurden automatisch neu gestartet
- Während Rolling Updates bekamen neue Pods erst Traffic wenn sie Ready waren
- Fehlerhafte Worker-Jobs wurden nach `backoff_limit: 3` Versuchen als Failed markiert

**Besonders wertvoll:** Die Kombination aus `maxUnavailable: 0` und `maxSurge: 1` in der Rolling Update Strategie garantierte, dass der API Gateway während aller Deployments durchgehend erreichbar war.

**Konkretes Beispiel:** Während eines Updates des API Gateway (Image-Rebuild wegen Bugfix) lief folgendes ab:

1. Neuer Pod startet → Readiness Probe: Not Ready
2. Service sendet Traffic weiterhin nur zu alten Pods
3. Neuer Pod vollständig gestartet → Readiness Probe: Ready
4. Service verteilt Traffic auf alte + neue Pods
5. Alter Pod wird terminiert
6. **Ergebnis:** Zero Downtime, kein einziger Failed Request

Dies wurde nicht manuell konfiguriert — es ist Kubernetes' Standard-Verhalten bei korrekter Health Probe Definition.

---

## 5. Kubernetes Jobs für Batch-Workloads

Die Entscheidung, Kubernetes Jobs statt eines dauerhaft laufenden Worker-Deployments zu verwenden, hat sich als die richtige Architektur-Entscheidung erwiesen:

- Ressourcen werden nur während des Transcodings belegt und danach freigegeben
- Jeder Job ist isoliert — ein fehlschlagender Job beeinflusst andere nicht
- Das Retry-System (`backoff_limit: 3`) ist built-in, ohne eigene Queue-Logik
- Die automatische Cleanup-TTL (`ttl_seconds_after_finished: 86400`) hält den Cluster sauber

**Skalierung ohne zusätzliche Arbeit:** Mehrere gleichzeitige Uploads erzeugen mehrere parallele Jobs. Kubernetes verteilt die Pods automatisch auf die verfügbaren Nodes — kein eigenes Queue-Management oder Worker-Pool nötig.

---

## 6. Dokumentation parallel zur Entwicklung

Die Entscheidung, Dokumentation direkt nach jeder implementierten Komponente zu schreiben (nicht am Ende), hat mehrere Vorteile gezeigt:

- Architektur-Entscheidungen werden im Kontext dokumentiert, solange die Überlegungen noch frisch sind
- Debugging-Sessions und ihre Lösungen werden nicht vergessen
- Die Dokumentation dient als Checkpoint: Wenn etwas schwer zu erklären ist, ist es oft auch schlecht designed

Das bedeutet: Die Dokumentation in `docs/04-implementation/` entstand direkt nach jedem Feature — nicht als nachträgliche Aufgabe am Projektende.

---

**Erstellt:** 19.04.2026  
**Kapitel abgeschlossen:** Lokales Deployment vollständig dokumentiert