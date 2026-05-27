# Storage-Abstraktion: GCSClient + S3Client

**Datum:** 27.05.2026
**Status:** ✅ Implementiert und produktiv

---

## Problemstellung

Die ursprüngliche Implementierung nutzte boto3 mit HMAC Keys für GCS — dies ermöglichte zwar Cloud-Agnostik (gleicher boto3-Code für MinIO und GCS), brachte aber erhebliche Nachteile mit sich:

- HMAC Keys müssen manuell erstellt und rotiert werden
- Kubernetes Secret `gcs-hmac-credentials` im Cluster notwendig
- Reihenfolge-Abhängigkeit: Namespace muss vor `terraform apply` existieren
- Mehrere Debugging-Stunden wegen falsch benannter Secret-Keys

Die Frage: Gibt es einen Weg, der sowohl **GCP Best Practices** (Workload Identity, kein Secret) als auch **Cloud-Agnostik** (gleiche Plattform auf GCP und StackIT) erfüllt?

---

## Lösung: Abstrakte StorageClient-Klasse

Statt einen gemeinsamen Code-Pfad zu erzwingen, wird eine abstrakte Schnittstelle definiert, die pro Umgebung unterschiedlich implementiert wird:

```python
class StorageClient(ABC):
    @abstractmethod
    def upload_file(self, file_obj, bucket, key) -> bool: ...
    @abstractmethod
    def download_file(self, bucket, key, local_path) -> bool: ...
    @abstractmethod
    def file_exists(self, bucket, key) -> bool: ...
    @abstractmethod
    def get_file_url(self, bucket, key, expiration) -> Optional[str]: ...
    @abstractmethod
    def delete_file(self, bucket, key) -> bool: ...
```

Zwei Implementierungen:

### GCSClient — für GKE

```python
class GCSClient(StorageClient):
    def __init__(self):
        from google.cloud import storage
        self.client = storage.Client()
        # Kein Credential-Parameter nötig!
        # google-cloud-storage nutzt automatisch das GKE Workload Identity Token
```

- Nutzt `google-cloud-storage` Library (nicht boto3)
- Authentifizierung vollständig via GKE Workload Identity
- **Kein Secret im Cluster**, kein HMAC Key, kein Credential-Management

### S3Client — für MinIO (lokal) und StackIT

```python
class S3Client(StorageClient):
    def __init__(self):
        import boto3
        self.client = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
        )
```

- Nutzt boto3 mit S3-kompatibler API
- Funktioniert mit MinIO (`http://minio:9000`) und StackIT Object Storage
- Credentials via ENV-Variablen

### Factory-Funktion

```python
def get_storage_client() -> StorageClient:
    provider = os.getenv("STORAGE_PROVIDER", "s3")
    if provider == "gcs":
        return GCSClient()
    return S3Client()
```

Die Wahl des Backends erfolgt ausschließlich über eine ENV-Variable — kein Code-Change zwischen Umgebungen.

---

## Konfiguration pro Umgebung

| Umgebung | `STORAGE_PROVIDER` | Credentials |
|----------|-------------------|-------------|
| Lokal (Kind + MinIO) | `s3` | `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` |
| GKE (GCP) | `gcs` | Workload Identity (automatisch) |
| StackIT (geplant) | `s3` | `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` |

**GKE ConfigMap:**
```yaml
storage_provider: "gcs"
```

**Lokale ConfigMap / ENV:**
```yaml
storage_provider: "s3"
s3_endpoint: "http://minio:9000"
```

---

## Worker: Inline-Abstraktion

Der Transcoding Worker (`worker.py`) hat keine separate Datei für die Storage-Abstraktion — die `GCSBackend` und `S3Backend` Klassen sind direkt in `worker.py` definiert. Dies war eine bewusste Entscheidung: Der Worker ist ein eigenständiges Kubernetes Job-Image ohne Abhängigkeit auf gemeinsame Bibliotheken des API Gateways.

Die Logik ist identisch zum API Gateway — nur die Implementierung ist inline statt in einer separaten Datei.

---

## Trade-offs

**Vorteile:**
- GCP Best Practices: Workload Identity, kein Secret-Management
- Cloud-Agnostik erhalten: S3Client für MinIO/StackIT unverändert
- Gleicher Anwendungscode — nur ConfigMap ändert sich
- Einfaches Testing: Provider via ENV-Variable austauschbar

**Nachteile:**
- Zwei Libraries (`google-cloud-storage` + `boto3`) im selben Image
- Signed URLs für GCS erfordern einen Service Account Key oder Workload Identity mit `iam.serviceAccounts.signBlob` Permission — GCSClient nutzt daher `generate_signed_url` mit `version="v4"`
- Code-Duplikation: GCSBackend/S3Backend im Worker entsprechen GCSClient/S3Client im API Gateway

---

## Warum nicht boto3 für alles?

boto3 nutzt das AWS SigV4-Protokoll. GCS unterstützt dieses Protokoll über HMAC Keys — aber nicht über Workload Identity (GCP-natives OIDC-Token). Eine Kombination aus boto3 + Workload Identity ist technisch nicht möglich.

Die Alternative wäre gewesen, HMAC Keys beizubehalten und auf Workload Identity zu verzichten. Das widerspricht GCP Best Practices und erfordert dauerhaftes Credential-Management.

---

**Verwandte Dokumente:**
- [Storage-Strategie: Evolution von emptyDir zu Cloud-Storage](./storage-strategy.md)
- [GKE Challenges: HMAC Key Probleme](../06-lessons-learned/gke-challenges.md)