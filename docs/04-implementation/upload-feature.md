# Upload Feature - Implementation

**Datum:** 03.03.2026  
**Status:** ✅ Erfolgreich implementiert

---

## Was wurde implementiert?

### 1. Pydantic Models (`app/models/job.py`)

**Enums:**
- `TranscodingPreset`: Verfügbare Qualitäten (480p, 720p, 1080p, 4k)
- `JobStatus`: Job-Lifecycle (pending, running, completed, failed, cancelled)

**Models:**
- `UploadRequest`: Request-Validierung
- `JobResponse`: Response nach Upload
- `JobStatusResponse`: Detaillierte Job-Info
- `JobListResponse`: Liste von Jobs

**Features:**
- Automatische Validierung durch FastAPI
- API-Dokumentation in Swagger UI
- Type Safety

---

### 2. File Validators (`app/utils/validators.py`)

**Funktionen:**

1. **`validate_video_file()`**
   - Format-Check (Extension + MIME-Type)
   - Filename-Safety (Path Traversal Protection)
   - Erlaubte Formate: mp4, mov, avi, mkv, webm

2. **`validate_file_size()`**
   - Größen-Check nach Upload
   - Max 500MB (konfigurierbar)
   - Automatisches Cleanup bei Überschreitung

3. **`sanitize_filename()`**
   - Entfernt gefährliche Zeichen
   - Ersetzt Spaces mit Underscore

4. **`generate_unique_filename()`**
   - Format: `{timestamp}_{original_name}`
   - Verhindert Kollisionen
   - Beispiel: `1707411000_vacation_video.mp4`

**Security:**
- Path Traversal Protection (`..` blockiert)
- Filename Sanitization (nur alphanumerisch + `-_.`)
- Size Limits (Out-of-Memory Prevention)

---

### 3. Upload Router (`app/routers/upload.py`)

**Endpoint:** `POST /api/v1/upload`

**Parameter:**
- `file`: Video-Datei (multipart/form-data)
- `preset`: Transcoding-Qualität (optional, default: 720p)

**Workflow:**
```
1. Validate file format
   ↓
2. Generate unique filename
   ↓
3. Save to /tmp/uploads (chunked, async)
   ↓
4. Validate file size
   ↓
5. Generate job ID
   ↓
6. Return job info (status: pending)
```

**Features:**
- **Async File Writing**: Memory-effizient (1MB Chunks)
- **Error Handling**: Cleanup bei Fehlern
- **Unique Job IDs**: UUID-basiert
- **Logging**: Structured output für Debugging

**Test Endpoint:** `GET /api/v1/upload/test`
- Zeigt Konfiguration
- Verifiziert Router-Integration

---

## Technische Details

### Async File Upload
```python
async with aiofiles.open(upload_path, 'wb') as out_file:
    chunk_size = 1024 * 1024  # 1MB
    while content := await file.read(chunk_size):
        await out_file.write(content)
```

**Vorteile:**
- Nur 1MB im RAM (nicht ganze Datei)
- Keine Thread-Blockierung
- 10 gleichzeitige Uploads = nur 10MB RAM

**Walrus Operator (`:=`):**
- Assignment + Condition in einem
- Python 3.8+

---

### Error Handling
```python
try:
    # Save file
except Exception as e:
    if os.path.exists(upload_path):
        os.remove(upload_path)  # Cleanup!
    raise HTTPException(...)
```

**Wichtig:**
- Halb-gespeicherte Dateien werden gelöscht
- Speicher wird freigegeben
- User bekommt sinnvolle Fehlermeldung

---

## Testing

### Test 1: Upload Test Endpoint
```bash
curl http://localhost:8080/api/v1/upload/test
```

**Response:**
```json
{
  "message": "Upload endpoint is ready",
  "upload_dir": "/tmp/uploads",
  "max_upload_size_mb": 500,
  "allowed_formats": [".mp4", ".mov", ".avi", ".mkv", ".webm"]
}
```

---

### Test 2: Video Upload

**Swagger UI:**
1. POST /api/v1/upload
2. Choose File (test-video.mp4)
3. Preset: 720p
4. Execute

**Response (201 Created):**
```json
{
  "job_id": "transcode-abc123def456",
  "status": "pending",
  "input_filename": "test-video.mp4",
  "preset": "720p",
  "created_at": "2026-02-08T16:30:00.123456Z"
}
```

---

### Test 3: Logs Verification
```bash
kubectl logs -n video-transcoding -l app=api-gateway --tail=50
```

**Output:**
```
📹 Video uploaded: 1707411000_test-video.mp4
🆔 Job ID: transcode-abc123def456
🎯 Preset: 720p
📏 File size: 1.00 MB
```

---

### Test 4: File im Pod
```bash
# Loop durch alle Pods
for pod in $(kubectl get pods -n video-transcoding -l app=api-gateway -o jsonpath='{.items[*].metadata.name}'); do
  echo "=== Pod: $pod ==="
  kubectl exec -n video-transcoding $pod -- ls -lh /tmp/uploads/
done
```

**Ergebnis:**
- Datei in einem der Pods gefunden ✅
- Unique Filename: `1707411000_test-video.mp4` ✅

---

## Known Limitations

### emptyDir Storage (Pod-local)

**Problem:**
- Jeder Pod hat eigenes `/tmp/uploads`
- Datei nur in Pod verfügbar, der Upload verarbeitet hat
- Download könnte anderen Pod treffen → Datei nicht gefunden

**Lösung für Production:**

1. **MinIO (empfohlen)** - S3-compatible Object Storage
2. **PersistentVolume** - Shared Storage für alle Pods
3. **Session Affinity** - Gleicher Client → Gleicher Pod

**Für Development:** Aktuell OK, später implementieren

---

## Was fehlt noch?

❌ **Kubernetes Job Creation** - Jobs werden noch nicht erstellt  
❌ **Transcoding Worker** - Kein FFmpeg Container  
❌ **Shared Storage** - MinIO oder PV  
❌ **Job Status Endpoint** - Status abfragen  
❌ **Download Endpoint** - Videos runterladen  

---

## Nächste Schritte

### Phase 1: Kubernetes Job Creation
- Job Template erstellen
- Kubernetes Client integrieren
- Job aus Upload-Endpoint erstellen

### Phase 2: Transcoding Worker
- FFmpeg Container bauen
- Worker-Script (Python + FFmpeg)
- Input/Output Handling

### Phase 3: Shared Storage
- MinIO in Kubernetes deployen
- Oder: PersistentVolume konfigurieren
- Upload/Download auf Storage umstellen

---

**Erstellt:** 03.03.2026  
**Branch:** feature/upload-endpoint  
**Status:** Upload Feature complete, ready for Job Creation
