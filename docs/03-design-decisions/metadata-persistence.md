# Metadata-Persistenz: Kubernetes Job ENV vars vs. PostgreSQL

**Datum:** 19.04.2026
**Aktualisiert:** 10.06.2026 — TTL korrigiert
**Status:** Lokal implementiert (K8s ENV), Cloud geplant (PostgreSQL)

---

## Problemstellung

Nach dem Upload eines Videos und der Erstellung eines Kubernetes Jobs stellt sich die Frage: Wie wird die Verbindung zwischen `job_id` und den zugehörigen Metadaten (`output_key`, `preset`, Status) gespeichert?

Diese Information wird für zwei Endpoints benötigt:
- `GET /api/v1/jobs/{job_id}` — Status abfragen
- `GET /api/v1/download/{job_id}` — Presigned URL für Output generieren

---

## Lokale Lösung: Kubernetes Job als Metadata-Store

### Ansatz

Bei der Job-Erstellung werden alle relevanten Metadaten als ENV-Variablen in den Container geschrieben:

```python
env=[
    client.V1EnvVar(name="INPUT_KEY",    value=input_key),
    client.V1EnvVar(name="OUTPUT_KEY",   value=output_key),
    client.V1EnvVar(name="PRESET",       value=preset),
    client.V1EnvVar(name="JOB_ID",       value=job_id),
]
```

Diese ENV-Variablen sind Teil der Job-Spec und werden von Kubernetes im etcd gespeichert. Sie können jederzeit über die K8s API ausgelesen werden:

```python
job = k8s_client.read_namespaced_job(name=job_id, namespace=namespace)
env_vars = job.spec.template.spec.containers[0].env
env_map = {e.name: e.value for e in env_vars}

output_key = env_map.get("OUTPUT_KEY")
preset     = env_map.get("PRESET")
```

Der Job-Status wird aus den Kubernetes-internen Zählern abgeleitet:

```python
def _parse_job_status(job_status) -> str:
    active    = job_status.active    or 0
    succeeded = job_status.succeeded or 0
    failed    = job_status.failed    or 0

    if succeeded > 0:  return "completed"
    elif active > 0:   return "running"
    elif failed > 0:   return "failed"
    else:              return "pending"
```

### Vorteile

- Keine zusätzliche Infrastruktur (kein Datenbankserver)
- Kubernetes ist bereits Single Source of Truth für Job-Status
- Implementierung in unter einer Stunde möglich
- Funktioniert vollständig offline

### Limitationen

**TTL-Problem:** Jobs werden nach 1 Stunde automatisch gelöscht (`ttl_seconds_after_finished: 3600`). Danach sind die Metadaten nicht mehr über die K8s API abrufbar — Downloads sind dann nicht mehr möglich.

**Bewusste Entscheidung:** Die 1-Stunden-TTL ist für dieses PoC-Projekt ausreichend. Die Cluster werden nach Tests wieder heruntergefahren, Videos werden direkt nach dem Test heruntergeladen. Eine längere TTL würde nur bei dauerhaft laufenden Produktions-Clustern einen Mehrwert bringen.

**Keine Queries:** Es gibt keine Möglichkeit, Jobs nach Kriterien zu filtern (z.B. alle Jobs mit Preset `720p`, alle fehlgeschlagenen Jobs).

**Keine persistente Historie:** Nach dem Cluster-Neustart sind alle Job-Informationen verloren.

---

## Production-Lösung: PostgreSQL

### Warum PostgreSQL für die Cloud?

In einer produktiven Umgebung müssen Jobs länger als 1 Stunde abrufbar sein. Nutzer sollen Videos auch Stunden nach dem Upload herunterladen können. Eine relationale Datenbank löst alle Limitationen des K8s-Ansatzes.

**Schema:**

```sql
CREATE TABLE jobs (
    job_id       VARCHAR(100) PRIMARY KEY,
    status       VARCHAR(20)  NOT NULL,
    input_key    VARCHAR(255) NOT NULL,
    output_key   VARCHAR(255),
    preset       VARCHAR(20)  NOT NULL,
    created_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
```

### Deployment

**GCP (Cloud SQL):**
```hcl
resource "google_sql_database_instance" "transcoding" {
  name             = "transcoding-db"
  database_version = "POSTGRES_15"
  settings {
    tier = "db-f1-micro"
  }
}
```

**StackIT:** Analog mit dem StackIT managed PostgreSQL Flex Service.

### Warum nicht implementiert?

PostgreSQL wurde als bewusste Scoping-Entscheidung nicht implementiert:

- Die K8s-ENV-Vars Lösung ist für Demo und PoC ausreichend
- Cloud SQL / PostgreSQL Flex bringt zusätzliche Komplexität (Helm Chart, Migrations, SQLAlchemy, Connection Pooling)
- Der wissenschaftliche Fokus liegt auf der Kubernetes-Orchestrierung und Cloud-Agnostik, nicht auf Datenbankintegration
- Als Future Work dokumentiert und begründet

---

## Architektur-Vergleich

| Kriterium | K8s ENV (aktuell) | PostgreSQL (Future Work) |
|-----------|-----------------|-------------------|
| **Setup** | Keine | Terraform + Schema |
| **Persistenz** | 1h (TTL) | Dauerhaft |
| **Queries** | Nicht möglich | Vollständig |
| **Historie** | Nein | Ja |
| **Komplexität** | Minimal | Mittel |
| **Geeignet für** | PoC / Demo | Production |

---

**Erstellt:** 19.04.2026
**Nächstes Dokument:** [Transcoding-Technologie](./transcoding-technology.md)