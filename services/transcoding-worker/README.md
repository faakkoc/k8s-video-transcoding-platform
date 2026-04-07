# Transcoding Worker

**Datum:** 07.04.2026  
**Status:** In Entwicklung

---

## Übersicht

Der Transcoding Worker ist ein Python-basierter FFmpeg-Wrapper, der als Kubernetes Job läuft und Video-Transcoding durchführt.

### Funktionsweise

```
Kubernetes Job startet
    ↓
Worker liest ENV-Vars (INPUT_FILE, OUTPUT_FILE, PRESET)
    ↓
Validiert Input-Datei
    ↓
Führt FFmpeg mit Preset aus
    ↓
Validiert Output-Datei
    ↓
Exit 0 (Success) oder Exit 1 (Failure)
```

---

## Komponenten

### 1. `ffmpeg_presets.py`

Definiert Transcoding-Konfigurationen:

| Preset | Resolution | Video Bitrate | Audio Bitrate | Encoding Speed |
|--------|-----------|---------------|---------------|----------------|
| **480p** | 854x480 | 1000k | 96k | fast |
| **720p** | 1280x720 | 2500k | 128k | medium |
| **1080p** | 1920x1080 | 5000k | 192k | medium |
| **4k** | 3840x2160 | 15000k | 256k | slow |

**FFmpeg-Parameter pro Preset:**
- Video-Codec: H.264 (libx264)
- Audio-Codec: AAC
- Encoding-Preset: fast/medium/slow (Speed vs. Quality)
- Profile: main/high (Kompatibilität)
- FPS: 30
- faststart: Metadata am Anfang (für Web-Streaming)

### 2. `worker.py`

Hauptlogik des Workers:

**Workflow:**
1. Liest Environment-Variables
2. Validiert Input-Datei existiert
3. Baut FFmpeg-Command mit Preset
4. Führt FFmpeg aus
5. Validiert Output-Datei erstellt wurde
6. Exit mit Status-Code

**Exit Codes:**
- `0`: Erfolg
- `1`: Fehler (Input nicht gefunden, FFmpeg fehlgeschlagen, etc.)

**Dependencies:**
- Keine! Worker nutzt nur Python Standard Library

### 3. `Dockerfile`

Multi-Stage Build:
1. **Stage 1**: FFmpeg von `jrottenberg/ffmpeg:4.4-alpine`
2. **Stage 2**: Python 3.11 + FFmpeg kopiert

**Features:**
- Non-root User (`worker:1000`)
- Keine externen Dependencies
- FFmpeg pre-installed
- Security Best Practices

---

## Umgebungsvariablen

| Variable | Beschreibung | Beispiel |
|----------|--------------|----------|
| `INPUT_FILE` | Eingabe-Dateiname (in `/tmp/uploads`) | `1707500000_video.mp4` |
| `OUTPUT_FILE` | Ausgabe-Dateiname (für `/tmp/outputs`) | `1707500000_video_720p.mp4` |
| `PRESET` | Transcoding-Qualität | `720p` |
| `JOB_ID` | Kubernetes Job ID | `transcode-abc123` |

---

## Build & Test

### Lokal bauen

```bash
cd services/transcoding-worker

# Docker Image bauen
docker build -t transcoding-worker:latest .

# Testen (ohne Input-Datei, nur Validierung)
docker run --rm \
  -e INPUT_FILE=test.mp4 \
  -e OUTPUT_FILE=test_720p.mp4 \
  -e PRESET=720p \
  -e JOB_ID=test-job \
  transcoding-worker:latest
```

### In Kind laden

```bash
# Image in Kind-Cluster laden
kind load docker-image transcoding-worker:latest --name video-transcoding

# Verifizieren
docker exec -it video-transcoding-control-plane crictl images | grep transcoding-worker
```

### Mit echtem Video testen

```bash
# Test-Video erstellen (10 Sekunden, 1280x720)
ffmpeg -f lavfi -i testsrc=duration=10:size=1280x720:rate=30 \
       -c:v libx264 -pix_fmt yuv420p test-video.mp4

# In Container kopieren
docker run --rm \
  -v $(pwd)/test-video.mp4:/tmp/uploads/test-video.mp4 \
  -v $(pwd)/output:/tmp/outputs \
  -e INPUT_FILE=test-video.mp4 \
  -e OUTPUT_FILE=test_720p.mp4 \
  -e PRESET=720p \
  -e JOB_ID=test-local \
  transcoding-worker:latest

# Output prüfen
ls -lh output/test_720p.mp4
ffprobe output/test_720p.mp4
```

---

## FFmpeg-Details

### Verwendete FFmpeg-Parameter

```bash
ffmpeg \
  -i input.mp4 \              # Input
  -y \                         # Overwrite output
  -c:v libx264 \              # H.264 codec
  -b:v 2500k \                # Video bitrate
  -vf scale=1280x720 \        # Resolution
  -r 30 \                     # Frame rate
  -preset medium \            # Encoding speed
  -profile:v high \           # H.264 profile
  -c:a aac \                  # Audio codec
  -b:a 128k \                 # Audio bitrate
  -movflags +faststart \      # Web streaming
  output.mp4
```

### Warum H.264?

- **Kompatibilität**: Funktioniert überall (Browser, Mobile, TV)
- **Performance**: Hardware-Beschleunigung verfügbar
- **Dateigröße**: Gute Kompression
- **Qualität**: Ausreichend für die meisten Anwendungen

**Alternative: H.265 (HEVC)**
- Bessere Kompression (~50% kleiner)
- Höhere CPU-Last
- Weniger kompatibel
- Für 4K empfohlen

---

## Performance

### Geschwindigkeit (ca. Werte)

| Preset | Encoding Speed | Quality | Use Case |
|--------|----------------|---------|----------|
| **fast** | ~2-3x Realtime | Gut | Live-Streams |
| **medium** | ~1x Realtime | Sehr gut | Standard |
| **slow** | ~0.5x Realtime | Exzellent | Archivierung |

**Beispiel:** 10 Min Video mit `medium` Preset
- 480p: ~3-5 Minuten
- 720p: ~5-8 Minuten
- 1080p: ~8-12 Minuten
- 4k: ~20-30 Minuten

### Ressourcen-Nutzung

**CPU:**
- 480p/720p: ~0.5-1 Core
- 1080p: ~1-2 Cores
- 4k: ~2-4 Cores

**Memory:**
- 480p/720p: ~200-500 MB
- 1080p: ~500-1000 MB
- 4k: ~1-2 GB

**Kubernetes Resource Limits (aus API Gateway):**
```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "2000m"
```

Ausreichend für 1080p, könnte für 4k knapp werden.

---

## Troubleshooting

### Problem: FFmpeg not found

```bash
# Im Container prüfen
docker run --rm transcoding-worker:latest ffmpeg -version

# Sollte FFmpeg-Version zeigen
```

### Problem: Input file not found

**Ursache:** emptyDir ist per-Pod (siehe Dokumentation)

**Workaround:** Shared Storage (MinIO/PersistentVolume)

### Problem: Transcoding zu langsam

**Optionen:**
1. `preset: fast` nutzen (schneller, größere Dateien)
2. CPU-Limits erhöhen (mehr Cores)
3. GPU-Beschleunigung (NVIDIA NVENC)

---

## Nächste Schritte

1. **Testing:** Mit echtem Video end-to-end testen
2. **Shared Storage:** MinIO integrieren
3. **Progress Tracking:** FFmpeg Progress an API melden
4. **Error Handling:** Detailliertere Fehlermeldungen
5. **GPU Support:** NVIDIA GPU Transcoding

---

**Erstellt:** 07.04.2026  
**Status:** Bereit für Testing