# Metadata-Persistenz: Kubernetes Job ENV vars vs. PostgreSQL

**Datum:** 19.04.2026  
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

**TTL-Problem:** Jobs werden nach 24 Stunden automatisch gelöscht (`ttl_seconds_after_finished: 86400`). Danach sind die Metadaten nicht mehr über die K8s API abrufbar — Downloads sind dann nicht mehr möglich.

**Keine Queries:** Es gibt keine Möglichkeit, Jobs nach Kriterien zu filtern (z.B. alle Jobs mit Preset `720p`, alle fehlgeschlagenen Jobs).

**Keine persistente Historie:** Nach dem Cluster-Neustart sind alle Job-Informationen verloren.

### Bewusste Entscheidung

Diese Lösung wurde bewusst für das lokale Deployment gewählt. Das Ziel war es, die Plattform funktional vollständig zu machen ohne unnötige Infrastruktur-Komplexität einzuführen. Für einen lokalen Proof-of-Concept ist die 24-Stunden-TTL kein Problem — Videos werden direkt nach dem Test heruntergeladen.

---

## Production-Lösung: PostgreSQL

### Warum PostgreSQL für die Cloud?

In der Cloud-Umgebung müssen Jobs länger als 24 Stunden abrufbar sein. Nutzer sollen Videos auch Tage nach dem Upload herunterladen können. Eine relationale Datenbank löst alle Limitationen des K8s-Ansatzes.

**Schema:**

```sql
CREATE TABLE jobs (
    job_id       VARCHAR(100) PRIMARY KEY,
    status       VARCHAR(20)  NOT NULL,  -- pending, running, completed, failed
    input_key    VARCHAR(255) NOT NULL,
    output_key   VARCHAR(255),
    preset       VARCHAR(20)  NOT NULL,
    created_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
```

**Workflow mit PostgreSQL:**

```
Upload → Job erstellen → DB Insert (status: pending)
              ↓
        Job läuft → K8s Status polling → DB Update (status: running)
              ↓
        Job fertig → DB Update (status: completed, output_key: ...)
              ↓
        GET /download/{job_id} → DB Query → Presigned URL
```

### Deployment

**Lokal (wäre möglich mit Helm):**
```bash
helm install postgres bitnami/postgresql \
  --namespace video-transcoding \
  --set auth.postgresPassword=dev123
```

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

**StackIT:** Analog mit dem StackIT managed PostgreSQL Service.

### Warum nicht lokal?

PostgreSQL wurde bewusst nicht lokal eingeführt:

- Zusätzliche Komplexität (Helm Chart, Migrations, SQLAlchemy Setup)
- Für 24-Stunden-Tests übertrieben
- Cloud SQL ist managed — kein selbst verwalteter Datenbankserver lokal bringt keinen Lernmehrwert
- Die Architekturentscheidung ist dieselbe: Der Code-Unterschied ist minimal

---

## Architektur-Vergleich

| Kriterium | K8s ENV (lokal) | PostgreSQL (Cloud) |
|-----------|-----------------|-------------------|
| **Setup** | Keine | Terraform + Schema |
| **Persistenz** | 24h (TTL) | Dauerhaft |
| **Queries** | Nicht möglich | Vollständig |
| **Historie** | Nein | Ja |
| **Skalierung** | K8s-limitiert | Managed Service |
| **Komplexität** | Minimal | Mittel |
| **Geeignet für** | MVP / Demo | Production |

---

## Migration bei Cloud-Deployment

Der Übergang von K8s ENV zu PostgreSQL erfordert minimale Code-Änderungen:

```python
# Bisher (k8s_client.py):
job_data = get_job_status(job_id)  # liest K8s Job

# Neu (mit DB):
job_data = db.query(Job).filter_by(job_id=job_id).first()
if not job_data:  # Fallback für Jobs vor DB-Einführung
    job_data = get_job_status(job_id)
```

Die bestehenden Endpoints (`/jobs/{job_id}`, `/download/{job_id}`) bleiben unverändert — nur die Datenquelle wechselt.

---

**Erstellt:** 19.04.2026  
**Nächstes Dokument:** [Transcoding-Technologie](./transcoding-technology.md)