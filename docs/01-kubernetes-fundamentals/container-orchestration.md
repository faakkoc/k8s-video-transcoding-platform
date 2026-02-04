# Container-Orchestrierung mit Kubernetes

**Datum:** 04.02.2025  
**Status:** In Bearbeitung

---

## Motivation: Warum Container-Orchestrierung?

### Problem 1: Manuelles Container-Management

In einem traditionellen Setup mit Docker allein:

```bash
# Server 1
docker run -d api-service

# Server 2
docker run -d api-service

# Server 3
docker run -d api-service
```

**Herausforderungen:**
- ❌ Manuelle Verwaltung auf jedem Server
- ❌ Kein automatisches Failover bei Ausfall
- ❌ Load Balancing muss manuell konfiguriert werden
- ❌ Skalierung erfordert manuelle Intervention
- ❌ Updates führen zu Downtime
- ❌ Keine einheitliche Service-Discovery

### Problem 2: Medientechnik-spezifische Anforderungen

**Typische Anforderungen in Broadcast/Media-Workflows:**

1. **Burst Traffic**
   - Live-Events → plötzlich tausende gleichzeitige Uploads
   - Normale Zeit → wenig Last
   - → Benötigt automatische Skalierung

2. **Rechenintensive Jobs**
   - 4K-Transcoding benötigt signifikante CPU/GPU-Ressourcen
   - Jobs können Stunden dauern
   - → Benötigt dedizierte Worker mit Resource-Garantien

3. **Verschiedene Workload-Typen**
   - **Long-running Services:** API, Frontend (24/7 verfügbar)
   - **Batch Jobs:** Transcoding (on-demand)
   - **Scheduled Tasks:** Cleanup, Reports (cron-artig)
   - → Benötigt flexible Workload-Orchestrierung

4. **Hohe Verfügbarkeit**
   - Broadcast darf nicht ausfallen
   - Redundanz erforderlich
   - → Benötigt automatisches Failover

---

## Lösung: Kubernetes

### Was ist Kubernetes?

Kubernetes (K8s) ist ein Open-Source Container-Orchestrierungs-System, das:
- Container automatisch verteilt (Scheduling)
- Selbstheilende Systeme ermöglicht (Self-Healing)
- Horizontal skaliert (Auto-Scaling)
- Load Balancing bereitstellt
- Service Discovery automatisiert
- Rolling Updates ohne Downtime ermöglicht

### Kernkonzepte (wird in weiteren Dokumenten vertieft)

#### 1. Pod
Die kleinste deploybare Einheit in Kubernetes.
- Ein oder mehrere Container
- Teilen sich Netzwerk und Storage
- Ephemeral (vergänglich)

#### 2. Deployment
Deklarative Beschreibung des gewünschten Zustands.
- Anzahl der Replicas
- Container Images
- Resource Limits
- Update Strategy

#### 3. Service
Stabiler Netzwerk-Endpunkt für Pods.
- Abstrahiert dynamische Pod-IPs
- Load Balancing
- Service Discovery via DNS

#### 4. Job
One-off oder Batch-Workloads.
- Läuft bis zur Completion
- Automatische Restarts bei Failure
- Parallel Execution möglich

---

## Kubernetes für Video Transcoding

### Anwendungsfall: Video Transcoding Platform

**Szenario:**
- Nutzer laden Videos hoch
- Videos müssen in mehrere Formate transcodiert werden
- Transcoding dauert je nach Video-Länge unterschiedlich lang
- Peak-Zeiten vs. ruhige Zeiten

**Ohne Kubernetes:**
```
┌─────────────┐
│   Server    │ → Manuell provisioniert, feste Kapazität
│   (VM/EC2)  │ → Überprovisioniert für Peak oder
│   FFmpeg    │    unterprovisioniert in Ruhe-Zeiten
└─────────────┘
```

**Mit Kubernetes:**
```
┌──────────────────────────────────────┐
│         Kubernetes Cluster           │
│                                      │
│  ┌─────┐ ┌─────┐ ┌─────┐           │
│  │Pod 1│ │Pod 2│ │Pod 3│  ← Normal │
│  └─────┘ └─────┘ └─────┘           │
│                                      │
│  ┌─────┐ ┌─────┐ ┌─────┐           │
│  │Pod 4│ │Pod 5│ │Pod 6│  ← Peak   │
│  └─────┘ └─────┘ └─────┘   (auto)  │
└──────────────────────────────────────┘
```

**Vorteile:**
- ✅ Automatische Skalierung basierend auf Queue-Länge
- ✅ Jobs werden automatisch verteilt
- ✅ Fehlerhafte Jobs werden automatisch restarted
- ✅ Effizienter Resource-Einsatz (nur zahlen was genutzt wird)

---

## Vergleich: Traditional vs. Kubernetes

| Aspekt | Traditional (VMs) | Kubernetes |
|--------|-------------------|------------|
| **Deployment** | Manuell per SSH/Script | Deklarativ via YAML |
| **Skalierung** | Neue VMs starten (Minuten) | Neue Pods starten (Sekunden) |
| **Updates** | Service stoppen → Update → Service starten | Rolling Update ohne Downtime |
| **Failover** | Manuelles Erkennen & Handeln | Automatisch |
| **Load Balancing** | Externe LB-Konfiguration | Integriert |
| **Service Discovery** | Statische IPs/DNS-Einträge | Automatisch |
| **Resource-Nutzung** | Oft ineffizient (Über-/Unter-Provisionierung) | Optimal (Bin Packing) |

---

## Relevanz für diese Arbeit

In diesem Projekt wird Kubernetes verwendet, um:

1. **Microservices-Architektur** zu implementieren
   - API Gateway
   - Job Controller
   - Transcoding Workers
   - Frontend

2. **Automatische Skalierung** zu demonstrieren
   - Horizontal Pod Autoscaler für Worker
   - Basierend auf CPU/Memory oder Custom Metrics (Queue-Länge)

3. **Job-Orchestrierung** zu realisieren
   - Kubernetes Jobs für Transcoding-Tasks
   - Parallele Ausführung
   - Retry-Mechanismen

4. **Cloud-Agnostik** zu bleiben
   - Deployment auf GCP (GKE)
   - Deployment auf StackIT
   - Gleiche Manifests, unterschiedliche Cloud-Provider

---

## Nächste Schritte

In den folgenden Kapiteln wird vertieft:
- Kubernetes Architektur (Control Plane, Nodes, etc.)
- Praktische Implementierung der Konzepte
- Kubernetes-spezifische Patterns für Media-Workflows

---

## Quellen

- [Kubernetes Official Documentation](https://kubernetes.io/docs/)
- [CNCF Cloud Native Landscape](https://landscape.cncf.io/)
- [Kubernetes Patterns Book](https://www.redhat.com/en/resources/oreilly-kubernetes-patterns-cloud-native-apps)

---

**Nächstes Dokument:** [Kubernetes Architektur](./kubernetes-architecture.md) (folgt)
