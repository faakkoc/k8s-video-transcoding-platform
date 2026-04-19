# Herausforderungen und Lösungen

**Datum:** 19.04.2026  
**Status:** Abgeschlossen

---

## Überblick

Dieses Dokument beschreibt die drei größten technischen Herausforderungen während der Entwicklung der lokalen Video Transcoding Platform — inklusive Debugging-Prozess, Root Cause und konkreten Learnings.

---

## 1. Der ENTRYPOINT-Bug (09.04. – 12.04.2026)

### Symptom

Worker Pods crashten sofort nach dem Start mit folgendem Log-Output:

```
[NULL @ 0x...] Unable to find a suitable output format for 'python'
python: Invalid argument
```

### Erste Diagnose: Falscher Verdacht

Die erste Reaktion war, das Problem im Image-Loading zu suchen. Folgende Maßnahmen wurden über 2-3 Stunden versucht:

- `kind load docker-image` mehrfach wiederholt
- Image-IDs auf allen Nodes geprüft (`crictl images`)
- Images auf Nodes manuell gelöscht (`crictl rmi`) — ohne Erfolg
- Kind-Cluster komplett neu erstellt — ohne Erfolg
- Neuer Image-Tag `:v2` statt `:latest` — gleicher Fehler
- Direct `ctr import` in containerd — funktioniert nicht

**Ergebnis nach 2-3 Stunden:** Keine Lösung. Das Image-Loading war nie das Problem.

### Root Cause

Das Base Image `jrottenberg/ffmpeg:4.4-ubuntu` setzt einen ENTRYPOINT:

```dockerfile
# Im Base Image (nicht sichtbar ohne docker inspect):
ENTRYPOINT ["ffmpeg"]
```

Docker kombiniert ENTRYPOINT und CMD. Unser Dockerfile:

```dockerfile
FROM jrottenberg/ffmpeg:4.4-ubuntu
# ...
CMD ["python", "worker.py"]
```

Ergibt beim Container-Start:

```bash
# Was tatsächlich ausgeführt wurde:
ffmpeg python worker.py

# Was ausgeführt werden sollte:
python worker.py
```

FFmpeg interpretierte `python` als Output-Format-Argument — daher "Unable to find a suitable output format for 'python'". Die Fehlermeldung beschrieb exakt das Problem, wurde aber nicht als Hinweis auf FFmpeg erkannt.

### Fix

```dockerfile
# CRITICAL: Override base image ENTRYPOINT
# Without this, CMD becomes arguments to ffmpeg → crash
ENTRYPOINT []
CMD ["python", "worker.py"]
```

### Timeline

| Datum | Session | Dauer | Ergebnis |
|-------|---------|-------|---------|
| 09.04.2026 | Debugging mit Sonnet 4.5 | ~3 Stunden | Keine Lösung |
| 12.04.2026 | Neue Session mit Opus | ~5 Minuten | Bug identifiziert und behoben |

### Learnings

**1. Base Image immer inspizieren:**
```bash
docker inspect jrottenberg/ffmpeg:4.4-ubuntu | grep -A2 Entrypoint
# → "Entrypoint": ["ffmpeg"]
```

**2. Fehlermeldungen wörtlich nehmen:** Die Fehlermeldung sagte "Unable to find a suitable output format for 'python'" — das bedeutete, FFmpeg suchte nach einem Output-Format namens "python". Ein klares Signal, dass FFmpeg (nicht Python) am Laufen war. Diese Information wurde ignoriert, weil die Vermutung "Image-Loading-Problem" zu dominant war (Confirmation Bias).

**3. ENTRYPOINT wird in Multi-Stage Builds vererbt** — auch wenn nur Dateien aus dem Base Image kopiert werden.

**4. Bei hartnäckigen Bugs: Problemdiagnose hinterfragen.** Nach einer Stunde ohne Fortschritt lohnt es sich zu fragen: "Ist das überhaupt das richtige Problem?"

---

## 2. emptyDir Multi-Pod Isolation (Februar – April 2026)

### Symptom

Nach der Integration von API Gateway und Transcoding Worker fand der Worker die Input-Datei nicht:

```
[ERROR] Input file not found: /tmp/uploads/1775601709_test-video.mp4
```

Die Datei war nach dem Upload im API Gateway Pod korrekt gespeichert — aber im Worker Pod nicht vorhanden.

### Root Cause

`emptyDir` Volumes sind per-Pod isoliert. Jeder Pod bekommt beim Start ein eigenes, leeres temporäres Verzeichnis:

```
API Gateway Pod A:
  /tmp/uploads/video.mp4  ✓ (existiert, wurde hochgeladen)

Worker Pod (separater Pod):
  /tmp/uploads/            ✗ (leer — eigenes emptyDir!)
```

Dies ist kein Bug, sondern das erwartete Kubernetes-Verhalten. `emptyDir` ist für temporäre Daten innerhalb eines einzelnen Pods gedacht, nicht für die Kommunikation zwischen Pods.

### Bewusste Entscheidung

Das Problem war bereits bei der Planung bekannt und wurde als bewusste technische Schuld akzeptiert:

1. Der Job-Creation-Workflow sollte zuerst demonstriert werden
2. Das Storage-Problem wurde parallel dokumentiert
3. MinIO als S3-kompatibler Shared Storage war von Anfang an als Lösung geplant

### Lösung

MinIO als Object Storage löst das Problem vollständig. Statt lokaler Dateien kommunizieren API Gateway und Worker über MinIO:

```
API Gateway: upload → s3://uploads/video.mp4
Worker:      download ← s3://uploads/video.mp4
Worker:      upload → s3://outputs/video_720p.mp4
```

Beide Pods greifen auf denselben Storage zu — unabhängig davon, auf welchem Node sie laufen.

### Learning

Bei Multi-Pod-Workflows in Kubernetes niemals davon ausgehen, dass Pods ein gemeinsames Filesystem haben. Shared State muss immer über ein externes System gehen: Object Storage, Datenbank, Message Queue oder PersistentVolume mit ReadWriteMany.

---

## 3. Kind Image Caching mit `:latest` Tag (März 2026)

### Symptom

Nach einem Rebuild des API Gateway Images wurde beim Deployment weiterhin die alte Version ausgeführt, obwohl `kind load docker-image` erfolgreich war.

### Root Cause

Kind cached Images nach Image-ID, nicht nach Tag. Der `:latest` Tag zeigt nach einem Rebuild auf eine neue Image-ID — aber Kubernetes entscheidet anhand von `imagePullPolicy`, ob ein neues Image gezogen wird.

Mit `imagePullPolicy: IfNotPresent` und `kind load` kann es zu inkonsistenten Zuständen kommen: Der Tag `:latest` zeigt auf das neue Image, aber einzelne Nodes haben noch das alte Image gecacht.

### Debugging-Versuche

- `crictl rmi` auf Nodes — funktioniert nicht zuverlässig
- Cluster-Neustart — alle Images verloren, aufwändig
- Verschiedene `kind load` Varianten — inkonsistent

### Lösung

```bash
# Image laden
kind load docker-image api-gateway:latest --name video-transcoding

# Deployment explizit neu starten → zieht das neu geladene Image
kubectl rollout restart deployment/api-gateway -n video-transcoding

# Warten bis fertig
kubectl rollout status deployment/api-gateway -n video-transcoding
```

`kubectl rollout restart` erstellt neue Pod-Definitionen und Kubernetes startet die Pods neu — dabei wird das frisch geladene Image aus dem lokalen Node-Cache verwendet.

### Learning

Für lokale Entwicklung mit Kind: nach jedem `kind load` immer `kubectl rollout restart` ausführen. In Production entfällt dieses Problem vollständig — dort wird immer aus der Registry gepullt, und versionierte Tags (`:v1.2.3` statt `:latest`) verhindern Caching-Probleme.

---

**Erstellt:** 19.04.2026  
**Nächstes Dokument:** [Was gut funktioniert hat](./what-worked-well.md)