# Service-Patterns

**Datum:** 04.02.2025
**Status:** Abgeschlossen

---

## API Gateway Pattern

Der API Gateway ist der einzige Einstiegspunkt für externe Clients. Er
bündelt alle Operationen (Upload, Status, Download) in einer einzigen
REST-API und kapselt die interne Komplexität (Kubernetes API, Storage).

```
Client
  │
  ▼
API Gateway (FastAPI)    ← Einziger öffentlicher Endpunkt
  │
  ├─ /api/v1/upload      → Kubernetes Job erstellen
  ├─ /api/v1/jobs/{id}   → K8s API abfragen
  └─ /api/v1/download/{id} → Storage URL generieren
```

**Vorteile:**
- Client muss Kubernetes-Internas nicht kennen
- Authentifizierung/Validierung zentral
- Internes Refactoring ohne API-Änderung möglich

---

## Sidecar Pattern (nicht implementiert)

Ein Sidecar-Container läuft im selben Pod wie der Hauptcontainer und
übernimmt Querschnittsaufgaben (Logging, Monitoring, mTLS). In diesem
Projekt nicht implementiert — Logging erfolgt direkt via Python `logging`
nach stdout (von Kubernetes gesammelt).

---

## Strangler Fig Pattern (für Migration)

Schrittweise Migration von Monolith zu Microservices. Nicht direkt
angewendet, aber relevant als Hintergrundwissen: dieses Projekt startete
mit einer monolithischen Konzeption und wurde schrittweise in Services
aufgeteilt (API Gateway + Worker).

---

## Storage-Abstraktion als Service-Pattern

Die `StorageClient`-Abstraktion (`storage_client.py`) ist ein Beispiel
des **Strategy Patterns**: das Interface (`StorageClient` ABC) ist stabil,
die Implementierung (`GCSClient` vs. `S3Client`) wird zur Laufzeit
via `STORAGE_PROVIDER`-ENV ausgewählt.

```python
# Interface (stabil)
class StorageClient(ABC):
    def upload_file(...) -> bool: ...
    def get_file_url(...) -> str: ...

# Implementierungen (austauschbar)
class GCSClient(StorageClient): ...   # GKE
class S3Client(StorageClient):  ...   # StackIT, lokal

# Selektion zur Laufzeit
def get_storage_client() -> StorageClient:
    if os.getenv("STORAGE_PROVIDER") == "gcs":
        return GCSClient()
    return S3Client()
```

Dieses Pattern ist der technische Kern der Cloud-Agnostik — detailliert
dokumentiert in [`storage-abstraction.md`](../03-design-decisions/storage-abstraction.md).