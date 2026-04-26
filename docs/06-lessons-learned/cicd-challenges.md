# CI/CD Challenges & Lessons Learned

**Datum:** 26.04.2026
**Status:** Abgeschlossen

---

## Übersicht

Die Einrichtung der CI/CD Pipeline war mit mehreren unerwarteten Hürden verbunden. Dieses Dokument protokolliert alle aufgetretenen Probleme chronologisch mit Root Cause Analysis und Fix.

---

## Challenge 1: terraform.auto.tfvars nicht im Repository

**Symptom:** `terraform plan` in der Pipeline hängt endlos ohne Output — wartet auf interaktive Eingabe der fehlenden Variablen.

**Ursache:** `terraform.auto.tfvars` lag in `.gitignore` da die Datei ursprünglich sensitive Werte enthalten sollte. In der Pipeline ist diese Datei nicht verfügbar, Terraform wartet auf manuelle Eingabe aller Variablen.

**Fix:** Da die Datei ausschließlich nicht-sensitive Konfigurationswerte enthält (Projekt-ID, Region, Bucket-Namen), wurde sie aus `.gitignore` entfernt und ins Repository eingecheckt:

```hcl
# terraform.auto.tfvars — keine sensitiven Werte
project_id             = "k8s-transcoding-plattform"
region                 = "us-central1"
cluster_name           = "video-transcoding"
uploads_bucket_name    = "k8s-transcoding-uploads"
outputs_bucket_name    = "k8s-transcoding-outputs"
artifact_registry_name = "transcoding"
github_repository      = "faakkoc/k8s-video-transcoding-platform"
```

Sensitive Werte wie HMAC Keys oder Passwörter gehören nie in `terraform.auto.tfvars` — sie werden über `terraform output` als GitHub Secrets hinterlegt oder direkt von Terraform als Kubernetes Secrets erstellt.

**Learning:** Die Entscheidung was in `.gitignore` gehört sollte explizit begründet werden. Nicht-sensitive Konfigurationsdateien müssen im Repo sein damit die Pipeline reproduzierbar ist.

---

## Challenge 2: Terraform State Lock nach abgebrochenem Pipeline-Run

**Symptom:** `terraform plan` schlägt fehl mit:

```
Error: Error acquiring the state lock
Lock Info:
  ID: 1776804057418350
  Operation: OperationTypePlan
  Who: runner@runnervmeorf1
```

**Ursache:** Der erste Pipeline-Run hatte `terraform plan` gestartet, der Job wurde aber abgebrochen (Timeout nach langem Hängen durch fehlende Variablen). Der GCS State Lock wurde nie freigegeben.

**Fix:** Lock direkt aus dem GCS Bucket löschen:

GCP Console → Cloud Storage → `k8s-transcoding-tfstate` → `terraform/state/` → `default.tflock` löschen

Der Befehl `terraform force-unlock <ID>` funktioniert nur für lokalen State, nicht für Remote State in GCS.

**Learning:** Bei abgebrochenen Terraform-Runs immer prüfen ob ein State Lock zurückgeblieben ist. Der Lock liegt als Datei im GCS Bucket und kann direkt gelöscht werden.

---

## Challenge 3: WIF Pool durch terraform destroy gelöscht — 30-Tage Hold

**Symptom:** Nach `terraform destroy` und erneutem `terraform apply`:

```
Error: Error creating WorkloadIdentityPool:
googleapi: Error 409: Requested entity already exists
```

**Ursache:** GCP löscht WIF Pools nicht sofort — sie werden 30 Tage lang im "deleted" State gehalten bevor sie endgültig entfernt werden. In dieser Zeit kann weder ein Pool mit derselben ID erstellt noch der bestehende Pool importiert werden.

**Fix:** Neue Pool-ID verwenden (`github-actions-pool-v2`, `github-actions-provider-v2`). Das GitHub Secret `WIF_PROVIDER` muss danach aktualisiert werden.

**Langfristige Lösung:** `prevent_destroy = true` auf allen WIF-Ressourcen verhindert dass `terraform destroy` diese Ressourcen löscht. Nach diesem Fix überlebt der WIF Pool alle zukünftigen `terraform destroy` Ausführungen.

**Learning:** GCP hat für sicherheitskritische Ressourcen wie WIF Pools Lösch-Verzögerungen eingebaut. `prevent_destroy` ist bei CI/CD Infrastruktur nicht optional.

---

## Challenge 4: serviceusage.googleapis.com API nicht aktiviert

**Symptom:** `terraform plan` in der Pipeline schlägt fehl mit:

```
Error 403: Service Usage API has not been used in project
before or it is disabled.
  with google_project_service.apis["container.googleapis.com"]
```

**Ursache:** Der CI/CD Service Account versucht über die Service Usage API zu prüfen welche GCP APIs aktiviert sind (`google_project_service` Ressourcen). Die Service Usage API selbst muss aber aktiviert sein damit das funktioniert — ein klassisches Hühner-Ei-Problem.

Lokal funktioniert `terraform plan` weil der eigene GCP-User die API bereits aktiviert hat. Der CI/CD Service Account hatte diese Berechtigung nicht.

**Fix in zwei Schritten:**

1. `serviceusage.googleapis.com` zur Liste der aktivierten APIs in `apis.tf` hinzufügen:
```hcl
resource "google_project_service" "apis" {
  for_each = toset([
    ...
    "serviceusage.googleapis.com",  # ← neu
  ])
}
```

2. Lokal anwenden damit die API aktiviert wird:
```fish
terraform apply -target=google_project_service.apis
```

**Learning:** Beim Design der Terraform-Konfiguration muss `serviceusage.googleapis.com` immer explizit aktiviert werden wenn Terraform `google_project_service` Ressourcen verwaltet. Ohne diese API kann Terraform den Status anderer APIs nicht lesen.

---

## Challenge 5: Artifact Registry nach terraform destroy leer

**Symptom:** Pipeline schlägt beim Docker Push fehl:

```
denied: Permission 'artifactregistry.repositories.uploadArtifacts'
denied on resource (or it may not exist).
```

Oder:

```
name unknown: Repository "transcoding" not found
```

**Ursache:** `terraform destroy` hat die Artifact Registry inklusive aller Images gelöscht. Die IAM-Binding für den CI/CD Service Account war ebenfalls weg.

**Fix:** `prevent_destroy = true` auf der Artifact Registry Ressource verhindert zukünftige versehentliche Löschungen:

```hcl
resource "google_artifact_registry_repository" "transcoding" {
  lifecycle {
    prevent_destroy = true
  }
}
```

**Learning:** Die Artifact Registry sollte wie ein dauerhafter Bestandteil der Infrastruktur behandelt werden, nicht als temporäre Ressource. Images repräsentieren produktiven Code und sollten nicht bei jedem `terraform destroy` verloren gehen.

---

## Challenge 6: terraform fmt schlägt in Pipeline fehl

**Symptom:**

```
Error: Terraform exited with code 3.
storage.tf
terraform.auto.tfvars
```

**Ursache:** `terraform fmt -check -recursive` schlägt fehl wenn Dateien nicht korrekt formatiert sind. `storage.tf` und `terraform.auto.tfvars` hatten inkonsistente Einrückung.

**Fix:** Lokal formatieren und committen:

```fish
cd terraform/gcp
terraform fmt -recursive
git add terraform/gcp/
git commit -m "fix: terraform fmt"
git push
```

**Learning:** `terraform fmt` sollte lokal vor jedem Commit ausgeführt werden. Ein pre-commit Hook könnte das automatisieren. In der Pipeline prüft `-check` nur — Änderungen müssen lokal gemacht und committed werden.

---

## Challenge 7: GKE Cluster Zonen-Konflikt bei terraform apply

**Symptom:**

```
Error: Cluster location change not allowed.
Current locations [us-central1-a us-central1-b us-central1-c],
new locations [us-central1-a us-central1-b us-central1-c us-central1-f].
```

**Ursache:** Das verwendete GKE Terraform Modul (`terraform-google-modules/kubernetes-engine`) hat automatisch die verfügbaren Zonen in `us-central1` abgefragt. GCP hatte in der Zwischenzeit Zone `us-central1-f` hinzugefügt. Ein laufender GKE Cluster kann seine Zonen nicht ändern.

**Status:** Nicht kritisch, noch nicht behoben. Der Fix wäre `node_locations` in `gke.tf` explizit zu setzen:

```hcl
node_locations = ["us-central1-a", "us-central1-b", "us-central1-c"]
```

Da `terraform apply` über die Pipeline nur den Cluster neu erstellt (nicht updated) ist der Fehler beim nächsten vollständigen Apply irrelevant — der neue Cluster wird mit den aktuellen Zonen erstellt.

---

## Zusammenfassung

| Challenge | Root Cause | Kategorie |
|-----------|------------|-----------|
| tfvars nicht im Repo | Falsche .gitignore Entscheidung | Konfiguration |
| State Lock | Abgebrochener Pipeline-Run | Prozess |
| WIF Pool 30-Tage Hold | GCP Sicherheits-Feature | GCP Verhalten |
| serviceusage API | Hühner-Ei-Problem bei API-Aktivierung | IAM/APIs |
| Artifact Registry leer | terraform destroy ohne prevent_destroy | Infrastruktur |
| terraform fmt | Fehlende lokale Formatierung | Code-Qualität |
| GKE Zonen-Konflikt | Dynamische Zonen-Auflösung im Modul | Terraform Modul |

**Übergreifendes Learning:** CI/CD Setup ist iterativ — viele Probleme zeigen sich erst im echten Pipeline-Run. `prevent_destroy` auf allen CI/CD-kritischen Ressourcen ist essentiell und sollte von Anfang an gesetzt werden. Der Zyklus `terraform destroy` / `terraform apply` zum Kostensparen funktioniert nur zuverlässig wenn die Pipeline-Infrastruktur explizit geschützt ist.
