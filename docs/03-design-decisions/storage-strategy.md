# Storage-Strategie: Von emptyDir zu Cloud-native Object Storage

**Datum:** 19.04.2026  
**Status:** Abgeschlossen (lokal), In Planung (Cloud)

---

## Problemstellung

Video-Transcoding ist ein Multi-Pod-Workflow: Der API Gateway Pod nimmt den Upload entgegen, ein separater Worker Pod führt das Transcoding durch. Beide Pods brauchen Zugriff auf dieselben Dateien — das ist das zentrale Storage-Problem dieser Architektur.

---

## Evolution der Storage-Lösung

### Stufe 1: emptyDir (MVP, gescheitert)

Der erste Ansatz nutzte `emptyDir` Volumes — temporäre Verzeichnisse die Kubernetes beim Pod-Start erstellt:

```yaml
volumes:
  - name: uploads
    emptyDir:
      sizeLimit: 10Gi
```

**Warum es nicht funktioniert:**

emptyDir ist per-Pod isoliert. Jeder Pod bekommt sein eigenes leeres Verzeichnis beim Start. Das bedeutet:

```
API Gateway Pod:
  /tmp/uploads/video.mp4  ✓ (existiert)

Worker Pod (anderer Pod!):
  /tmp/uploads/            ✗ (leer)
```

Dies wurde bewusst als erster Schritt akzeptiert, um den Job-Creation-Workflow zu demonstrieren bevor die Storage-Frage gelöst war. Die Limitation wurde dokumentiert und als technische Schuld behandelt.

**Learning:** Bei verteilten Systemen darf nie angenommen werden, dass Pods ein gemeinsames Filesystem teilen.

---

### Stufe 2: MinIO (lokale Production-Simulation)

MinIO ist ein S3-kompatibler Object Storage Server der als Kubernetes-Deployment läuft. Er löst das Multi-Pod-Problem vollständig: Alle Pods greifen über Netzwerk auf denselben Storage zu.

**Deployment via Helm:**

```bash
helm install minio minio/minio \
  --namespace video-transcoding \
  --set rootUser=minioadmin \
  --set rootPassword=minioadmin123 \
  --set mode=standalone \
  --set persistence.size=10Gi
```

**Warum MinIO für lokale Entwicklung?**

- S3-kompatible API → gleicher boto3-Code wie in der Cloud
- Läuft in Kubernetes → production-ähnliches Setup
- Kein Cloud-Account nötig → vollständig offline entwickelbar
- Eigene Console (Web UI) für einfaches Debugging

**Zwei Buckets:**

| Bucket | Zweck |
|--------|-------|
| `uploads` | Input-Videos nach dem Upload |
| `outputs` | Transcodierte Videos nach dem Job |

---

### Stufe 3: Cloud Object Storage (Production)

In der Cloud-Umgebung ersetzt ein managed Object Storage Service MinIO. Der entscheidende Vorteil: Der Anwendungscode ändert sich nicht — nur die Konfiguration.

| Parameter | Lokal (MinIO) | GCP | StackIT |
|-----------|---------------|-----|---------|
| `S3_ENDPOINT` | `http://minio:9000` | `https://storage.googleapis.com` | StackIT Endpoint |
| `S3_ACCESS_KEY` | `minioadmin` | Workload Identity | Service Account |
| `S3_SECRET_KEY` | `minioadmin123` | Workload Identity | Service Account |

**Warum Cloud Object Storage statt MinIO in der Cloud?**

- Managed Service → keine Wartung, automatische Redundanz
- Unbegrenzt skalierbar (kein Persistence-Size Limit)
- Pay-per-use → kosteneffizient
- Native IAM-Integration (Workload Identity, kein Passwort im Code)
- SLA-backed Verfügbarkeit

---

## Trade-off Analyse

| Kriterium | emptyDir | MinIO (lokal) | Cloud Storage |
|-----------|----------|---------------|---------------|
| **Multi-Pod Zugriff** | ❌ | ✅ | ✅ |
| **Setup-Aufwand** | Minimal | Mittel (Helm) | Gering (Terraform) |
| **Kosten** | Kostenlos | Kostenlos | ~$0.02/GB |
| **Skalierung** | Per-Pod limitiert | Node-limitiert | Unbegrenzt |
| **Wartung** | Keine | Selbst | Managed |
| **Offline-Entwicklung** | ✅ | ✅ | ❌ |
| **Cloud-Agnostik** | ✅ | ✅ | Abhängig vom Provider |

---

## Warum S3-API als Abstraktion?

Die Entscheidung boto3 mit der S3-API zu verwenden war zentral für die Cloud-Agnostik der Plattform. Die S3-API ist der De-facto-Standard für Object Storage — MinIO, Google Cloud Storage, AWS S3 und StackIT Object Storage implementieren alle dieselbe Schnittstelle.

```python
# Dieser Code funktioniert mit allen drei Backends unverändert:
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

Die einzige Änderung zwischen Umgebungen sind ENV-Variablen — kein Code-Change, nur Konfiguration.

---

## Bewusste technische Schulden

**emptyDir für lokales MVP:** Die Entscheidung mit emptyDir zu starten und MinIO erst später zu integrieren war bewusst. Sie erlaubte es, den Job-Creation-Workflow zu demonstrieren und zu testen bevor das Storage-Problem vollständig gelöst war. Die Limitation war von Anfang an bekannt und dokumentiert.

**Hardcoded Credentials lokal:** MinIO-Credentials (`minioadmin/minioadmin123`) sind direkt in den Kubernetes-Manifests hinterlegt. Für die lokale Entwicklung ist das akzeptabel — der Cluster ist nur lokal erreichbar und enthält keine echten Nutzerdaten.

Im Cloud-Deployment werden Credentials durch **Workload Identity** (GCP) bzw. **Service Accounts** (StackIT) ersetzt. Kubernetes Secrets werden nur als Übergangslösung genutzt — produktiv werden keine Credentials im Code gespeichert.

---

**Erstellt:** 19.04.2026  
**Nächstes Dokument:** [Metadata-Persistenz](./metadata-persistence.md)