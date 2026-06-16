# Kubernetes Architektur

**Datum:** 04.02.2025
**Status:** Abgeschlossen

---

## Überblick

Ein Kubernetes-Cluster besteht aus zwei Typen von Maschinen: dem **Control Plane**
(Steuerungsebene) und den **Worker Nodes** (Arbeitsknoten). Das Control Plane
trifft alle Entscheidungen — Scheduling, Skalierung, Self-Healing — während
Worker Nodes die Container tatsächlich ausführen.

```
┌─────────────────────────────────────────────────────────┐
│                     Control Plane                       │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  API Server  │  │  Scheduler   │  │  Controller  │  │
│  │ (kube-apiserver)│  │              │  │  Manager     │  │
│  └──────┬───────┘  └──────────────┘  └──────────────┘  │
│         │                                               │
│  ┌──────▼───────┐                                       │
│  │     etcd     │  ← Cluster-Zustand (Key-Value Store)  │
│  └──────────────┘                                       │
└─────────────────────────────────────────────────────────┘
              │ kubectl / API calls
┌─────────────▼───────────────────────────────────────────┐
│                     Worker Nodes                        │
│                                                         │
│  ┌──────────────────────────────────────┐               │
│  │  Node 1                              │               │
│  │  ┌──────────┐  ┌──────────────────┐  │               │
│  │  │  kubelet │  │  Container       │  │               │
│  │  │          │  │  Runtime         │  │               │
│  │  └──────────┘  └──────────────────┘  │               │
│  │  ┌──────────┐  ┌──────────────────┐  │               │
│  │  │  Pod A   │  │  Pod B           │  │               │
│  │  └──────────┘  └──────────────────┘  │               │
│  └──────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
```

---

## Control Plane Komponenten

### API Server (`kube-apiserver`)
Einziger Einstiegspunkt für alle Kubernetes-Operationen. Jede Aktion —
`kubectl apply`, CI/CD Pipeline, interner Controller — geht durch den API Server.
Validiert Requests und schreibt den gewünschten Zustand in etcd.

### etcd
Verteilter Key-Value-Store, der den gesamten Cluster-Zustand speichert:
welche Pods laufen sollen, welche Services existieren, welche ConfigMaps
vorhanden sind. Bei Cluster-Neustart wird der Zustand aus etcd wiederhergestellt.

> **Relevanz für dieses Projekt:** Job-Metadaten (Input-Key, Output-Key, Preset)
> werden als ENV-Variablen in der Job-Spec gespeichert — direkt in etcd.
> Das ist die Grundlage des "K8s-as-Database"-Ansatzes in
> [`metadata-persistence.md`](../03-design-decisions/metadata-persistence.md).

### Scheduler (`kube-scheduler`)
Entscheidet, auf welchem Node ein neuer Pod laufen soll. Berücksichtigt
Ressourcen-Anforderungen (`requests`/`limits`), Node-Labels, Affinities und
aktuelle Auslastung. Bei GKE Autopilot wird der Scheduler durch Googles
Autopilot-Logik erweitert — er kann neue Nodes provisionieren wenn keine
passenden vorhanden sind.

### Controller Manager
Führt eine Reihe von Control Loops aus — jeder überwacht einen bestimmten
Ressourcentyp und stellt sicher, dass Ist-Zustand = Soll-Zustand:

- **Deployment Controller** — stellt sicher, dass die gewünschte Anzahl Replicas läuft
- **Job Controller** — überwacht Kubernetes Jobs, startet Pods, trackt Completion
- **ReplicaSet Controller** — verwaltet Pod-Replikation

---

## Worker Node Komponenten

### kubelet
Agent auf jedem Worker Node. Empfängt Pod-Specs vom API Server und stellt
sicher, dass die Container gestartet sind und laufen. Meldet Node-Status
und Pod-Status zurück an den API Server.

### Container Runtime
Führt Container aus. Kubernetes unterstützt mehrere Runtimes (containerd,
CRI-O). Docker wird als Runtime nicht mehr direkt unterstützt (seit K8s 1.24),
aber Docker-Images funktionieren weiterhin — das Image-Format ist standardisiert (OCI).

### kube-proxy
Netzwerk-Proxy auf jedem Node. Implementiert die Service-Abstraktion durch
iptables/ipvs-Regeln — sorgt dafür, dass Traffic an einen Service automatisch
auf die zugehörigen Pods verteilt wird.

---

## GKE Autopilot vs. Standard GKE

In diesem Projekt wird **GKE Autopilot** verwendet. Der Unterschied zum
Standard-GKE:

| Aspekt | Standard GKE | GKE Autopilot |
|--------|-------------|----------------|
| **Node-Verwaltung** | Manuell (Node Pool konfigurieren) | Vollautomatisch |
| **Skalierung** | HPA + Cluster Autoscaler konfigurieren | Eingebaut |
| **Kosten** | Pro Node (auch wenn leer) | Pro Pod (nur was genutzt wird) |
| **Control Plane** | Managed by Google | Managed by Google |
| **Worker Nodes** | Selbst verwaltet | Von Google verwaltet |
| **Einschränkungen** | Keine besonderen | Kein DaemonSet, eingeschränkte Hostpath |

**Warum Autopilot?** Für ein PoC-Projekt mit unregelmäßiger Last (Demo-Sessions,
Tests) ist Autopilot kosteneffizienter. Der Trade-off: 60–90s Cold-Start-Latenz
wenn kein Node verfügbar ist.

---

## Quellen

- [Kubernetes Komponenten (offizielle Doku)](https://kubernetes.io/docs/concepts/overview/components/)
- [GKE Autopilot Übersicht](https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview)