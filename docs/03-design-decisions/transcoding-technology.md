# Transcoding-Technologie: FFmpeg, Codecs und Preset-System

**Datum:** 19.04.2026  
**Status:** Abgeschlossen

---

## Problemstellung

Für eine Video Transcoding Platform müssen drei Technologie-Entscheidungen getroffen werden: Welches Tool führt das Transcoding durch, welcher Video-Codec wird verwendet, und wie werden verschiedene Ausgabequalitäten verwaltet?

---

## FFmpeg vs. Cloud Transcoding APIs

### Cloud Transcoding APIs

Cloud-Anbieter bieten managed Transcoding-Services an:

- **Google Transcoder API** — vollständig managed, skaliert automatisch
- **AWS Elemental MediaConvert** — production-grade, sehr mächtig
- **Azure Media Services** — Microsoft-Ökosystem

**Vorteile:**
- Keine eigene Infrastruktur für Transcoding nötig
- Automatische Skalierung
- Optimierte Hardware (oft GPU-basiert)
- SLA-backed

**Nachteile:**
- Kosten: Google Transcoder API ~$0.015 pro Minute Video
- Vendor Lock-in — Code ist nicht portierbar
- Weniger Kontrolle über Encoding-Parameter
- Widerspricht dem Cloud-Agnostik-Ziel des Projekts

### FFmpeg (gewählt)

FFmpeg ist das Standard-Open-Source-Tool für Video-Verarbeitung. Es läuft als Container-Prozess und wird von Kubernetes als Job orchestriert.

**Vorteile:**
- Open Source, kostenlos
- Volle Kontrolle über alle Encoding-Parameter
- Cloud-agnostisch — läuft überall wo Docker läuft
- Aktive Community, ausgezeichnete Dokumentation
- Hardware-Beschleunigung verfügbar (NVIDIA NVENC, Intel Quick Sync)

**Nachteile:**
- Muss selbst skaliert werden (durch Kubernetes Jobs gelöst)
- Kein managed Service — Infrastruktur muss betrieben werden

**Für dieses Projekt:** FFmpeg demonstriert Kubernetes-Job-Orchestrierung deutlich besser als eine Cloud API. Die Forschungsfrage ist nicht "wie transkodiert man Video", sondern "wie orchestriert Kubernetes rechenintensive Batch-Jobs".

---

## Codec-Wahl: H.264 vs. H.265

### H.264 (AVC) — gewählt

H.264 ist seit 2003 der Standard-Codec für Web-Video.

**Kompatibilität:**

| Plattform | H.264 | H.265 |
|-----------|-------|-------|
| Chrome | ✅ | ✅ (ab 2023) |
| Firefox | ✅ | ⚠️ (OS-abhängig) |
| Safari | ✅ | ✅ |
| iOS | ✅ | ✅ |
| Android | ✅ | ✅ (ab Android 5) |
| Smart TVs (alt) | ✅ | ❌ |

**Performance:**
- Encoding-Speed: 1x Realtime bei `medium` Preset
- Hardware-Beschleunigung: Verfügbar auf allen modernen GPUs
- CPU-Last: Moderat

### H.265 (HEVC)

**Vorteile gegenüber H.264:**
- ~50% bessere Kompression bei gleicher Qualität (z.B. 8 MB statt 4 MB)
- Besser für 4K-Inhalte geeignet

**Nachteile:**
- 2-3x höhere CPU-Last beim Encoding
- Lizenzprobleme (Patent-Pool, keine royalty-free Nutzung)
- Browser-Support nicht universell

**Entscheidung:** Für eine Web-Plattform ist universelle Kompatibilität wichtiger als Dateigröße. H.264 funktioniert auf jedem Gerät ohne Einschränkungen.

---

## Das Preset-System

### Design

Statt rohe FFmpeg-Befehle direkt zu konstruieren, wurde ein Preset-System implementiert:

```python
class FFmpegPreset:
    def __init__(self, resolution, video_bitrate, audio_bitrate,
                 codec, preset, profile, fps):
        ...

    def to_ffmpeg_args(self) -> List[str]:
        return [
            "-c:v", self.codec,
            "-b:v", self.video_bitrate,
            "-vf", f"scale={self.resolution}",
            "-r", str(self.fps),
            "-preset", self.preset,
            "-profile:v", self.profile,
            "-c:a", "aac",
            "-b:a", self.audio_bitrate,
            "-movflags", "+faststart",
        ]
```

**Warum ein Preset-System?**

- **Konsistenz:** Alle 720p-Videos haben exakt dieselben Encoding-Parameter
- **Wartbarkeit:** Eine Änderung an einem Preset wirkt sich überall aus
- **Erweiterbarkeit:** Neue Presets können ohne Code-Änderungen hinzugefügt werden
- **Validierung:** Nur bekannte Presets werden akzeptiert

### Implementierte Presets

| Preset | Auflösung | Video-Bitrate | Audio-Bitrate | Encoding-Speed | Anwendungsfall |
|--------|-----------|---------------|---------------|----------------|----------------|
| `480p` | 854×480 | 1000k | 96k | fast | Mobile, Low Bandwidth |
| `720p` | 1280×720 | 2500k | 128k | medium | Standard HD |
| `1080p` | 1920×1080 | 5000k | 192k | medium | Full HD |
| `4k` | 3840×2160 | 15000k | 256k | slow | Ultra HD |

### FFmpeg Encoding-Speed Parameter

FFmpeg unterscheidet zwischen Encoding-Geschwindigkeit und Ausgabequalität:

| Speed | Encoding-Zeit | Dateigröße | Qualität |
|-------|---------------|------------|----------|
| `fast` | ~2-3x Realtime | Größer | Gut |
| `medium` | ~1x Realtime | Mittel | Sehr gut |
| `slow` | ~0.5x Realtime | Kleiner | Exzellent |

`-movflags +faststart` verschiebt die MP4-Metadaten an den Dateianfang, sodass Videos im Browser gestreamt werden können bevor sie vollständig geladen sind.

---

## Base Image: Alpine vs. Ubuntu

### Problem mit Alpine

Der erste Ansatz nutzte einen Multi-Stage Build:

```dockerfile
FROM jrottenberg/ffmpeg:4.4-alpine AS ffmpeg
FROM python:3.11-slim
COPY --from=ffmpeg /usr/local /usr/local
```

**Ergebnis:** `ffmpeg: not found`

**Ursache:** Alpine Linux nutzt `musl libc`, Debian/Ubuntu nutzen `glibc`. Die FFmpeg-Binaries sind gegen `musl libc` kompiliert und laufen nicht im `glibc`-basierten Python-Image.

### Lösung: Ubuntu-basiertes Image

```dockerfile
FROM jrottenberg/ffmpeg:4.4-ubuntu

RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    ln -s /usr/bin/python3 /usr/bin/python
```

**Nachteil:** Größeres Image (~400 MB vs. ~150 MB Alpine)

**Abwägung:** Funktionalität vor Image-Größe. Für Development ist ein größeres Image akzeptabel. In Production könnte ein custom FFmpeg-Build das Image optimieren.

**Learning:** Bei Multi-Stage Builds immer auf Library-Kompatibilität achten. Alpine und Debian/Ubuntu sind nicht binär-kompatibel.

---

**Erstellt:** 19.04.2026  
**Nächstes Dokument:** [Kubernetes-Patterns](./kubernetes-patterns.md)