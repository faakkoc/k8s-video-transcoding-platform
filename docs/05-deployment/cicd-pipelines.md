# CI/CD Pipelines

**Datum:** 26.04.2026
**Status:** ✅ Funktionierend

---

## Übersicht

Die CI/CD Pipeline automatisiert den gesamten Build-, Test- und Deployment-Prozess der Video Transcoding Platform. Sie ist mit GitHub Actions implementiert und authentifiziert sich gegenüber GCP über Workload Identity Federation — ohne Service Account Keys im Repository.

Zwei Workflows sind implementiert:

| Workflow | Trigger | Zweck |
|----------|---------|-------|
| `build-and-test.yml` | Jeder Push, jeder PR auf `main` | Lint + Docker Build |
| `deploy-gcp.yml` | Push auf `main` + manuell | Build & Push + Terraform Plan + Apply |

---

## Authentifizierung: Workload Identity Federation

### Das Problem mit Service Account Keys

Der naive Ansatz für GCP-Authentifizierung aus GitHub Actions wäre ein Service Account Key (JSON-Datei) als GitHub Secret zu hinterlegen. Das hat mehrere Nachteile:

- Keys sind langlebig und müssen manuell rotiert werden
- Ein geleakter Key ermöglicht dauerhaften GCP-Zugriff
- Keys in Secrets sind schwerer zu auditieren als IAM-Bindings

### Workload Identity Federation als Lösung

Workload Identity Federation (WIF) ermöglicht GitHub Actions sich direkt über OIDC bei GCP zu authentifizieren — ohne langlebige Credentials. Der Ablauf:

```
GitHub Actions Runner startet Job
    │
    ▼
GitHub stellt OIDC-Token aus
(enthält: repository, branch, actor, sha)
    │
    ▼
GitHub Actions sendet Token an GCP
    │
    ▼
GCP validiert Token gegen WIF Pool/Provider
(prüft: kommt Token wirklich von GitHub? Stimmt das Repository?)
    │
    ▼
GCP stellt kurzlebiges Access Token aus
(gültig nur für die Dauer des Jobs)
    │
    ▼
GitHub Actions nutzt Token für GCP API Calls
(Artifact Registry, GKE, Terraform State)
```

### Terraform Konfiguration

WIF wird vollständig über Terraform provisioniert (`terraform/gcp/github-wif.tf`):

```hcl
# WIF Pool — Sammlung externer Identitäten
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-actions-pool-v2"
  display_name              = "GitHub Actions Pool"
}

# WIF Provider — definiert wie GitHub Tokens validiert werden
resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider-v2"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  # Nur Tokens aus diesem Repository werden akzeptiert
  attribute_condition = "assertion.repository == 'faakkoc/k8s-video-transcoding-platform'"
}
```

Der `attribute_condition` ist entscheidend für die Sicherheit: Nur OIDC-Tokens die aus dem korrekten GitHub Repository stammen werden akzeptiert.

### GitHub Secrets

Nach `terraform apply` werden zwei Werte als GitHub Repository Secrets hinterlegt:

```fish
# WIF Provider Resource Name
terraform output -raw workload_identity_provider
# → projects/1018020857087/locations/global/workloadIdentityPools/github-actions-pool-v2/providers/github-actions-provider-v2
# → GitHub Secret: WIF_PROVIDER

# CI/CD Service Account Email
terraform output -raw github_actions_service_account
# → github-actions-cicd@k8s-transcoding-plattform.iam.gserviceaccount.com
# → GitHub Secret: GCP_SERVICE_ACCOUNT
```

### CI/CD Service Account Berechtigungen

Der dedizierte `github-actions-cicd` Service Account hat nur die minimal notwendigen Berechtigungen:

| Rolle | Zweck |
|-------|-------|
| `artifactregistry.writer` | Docker Images pushen |
| `container.developer` | kubectl rollout restart |
| `storage.objectAdmin` | Terraform State lesen/schreiben |
| `editor` | Terraform apply (GCP Ressourcen verwalten) |
| `resourcemanager.projectIamAdmin` | IAM Bindings via Terraform |
| `serviceusage.serviceUsageAdmin` | GCP APIs via Terraform verwalten |

---

## Workflow 1: Build & Test (`build-and-test.yml`)

Läuft bei jedem Push auf jeden Branch und bei Pull Requests auf `main`.

```
Push/PR
    │
    ├─── Lint Python Code (ruff)
    │        ├── services/api-gateway/
    │        └── services/transcoding-worker/
    │
    ├─── Build API Gateway Image (kein Push)
    │
    └─── Build Transcoding Worker Image (kein Push)
```

**Zweck:** Früh Fehler erkennen — fehlerhafte Dockerfiles oder Linting-Fehler werden bereits vor dem Merge auf `main` aufgedeckt. Die Jobs laufen parallel für schnelles Feedback.

**Linting mit ruff:** `ruff` ist ein extrem schneller Python Linter (in Rust geschrieben). Er prüft auf unused imports, bare excepts, f-strings ohne Platzhalter und andere häufige Python-Fehler.

---

## Workflow 2: Deploy to GCP (`deploy-gcp.yml`)

### Trigger

```yaml
on:
  push:
    branches: [main]        # Automatisch bei Merge auf main
  workflow_dispatch:         # Manuell über GitHub UI
    inputs:
      apply:
        description: "Run terraform apply after plan?"
        type: choice
        options: ["false", "true"]
```

Jeder Merge auf `main` startet automatisch Build & Push + Terraform Plan. `terraform apply` wird bewusst nur manuell getriggert — so kann der Plan zuerst geprüft werden bevor Infrastruktur verändert wird.

### Job-Struktur

```
Push auf main
    │
    ▼
[Job 1] Build & Push Images (~2-3 Min)
    → Authenticate to GCP (WIF)
    → docker build api-gateway
    → docker push :latest + :<git-sha>
    → docker build transcoding-worker
    → docker push :latest + :<git-sha>
    │
    ▼ (needs: build-and-push)
[Job 2] Terraform Plan (~30s)
    → Authenticate to GCP (WIF)
    → terraform init
    → terraform fmt -check -recursive
    → terraform validate
    → terraform plan
    │
    ▼ (needs: terraform-plan)
    │   if: workflow_dispatch AND apply=true
[Job 3] Terraform Apply & Deploy
    → terraform apply -auto-approve
    → kubectl apply -f kubernetes/gke/
    → kubectl rollout restart deployment/api-gateway
    → kubectl rollout status deployment/api-gateway
```

### Doppeltes Tagging der Docker Images

Images werden mit zwei Tags gepusht:

```
api-gateway:latest          ← immer der aktuellste Stand
api-gateway:<git-sha>       ← eindeutig einem Commit zuordenbar
```

`:latest` wird vom GKE Deployment genutzt (`imagePullPolicy: Always`). Der SHA-Tag ermöglicht Rollbacks auf einen bestimmten Commit-Stand.

### Terraform fmt, validate und plan

```yaml
- name: Terraform Format Check
  run: terraform fmt -check -recursive

- name: Terraform Validate
  run: terraform validate

- name: Terraform Plan
  run: terraform plan
```

`terraform fmt -check` schlägt fehl wenn Dateien nicht korrekt formatiert sind — das erzwingt konsistente Formatierung im Repo. `terraform validate` prüft die Syntax ohne GCP API Calls. `terraform plan` zeigt welche Änderungen angewendet werden würden.

### Manueller Apply

Der `terraform apply` Job ist auf `workflow_dispatch` mit `apply=true` beschränkt:

```yaml
if: ${{ github.event_name == 'workflow_dispatch' && inputs.apply == 'true' }}
```

Das verhindert dass automatische Pushes unbeabsichtigt Infrastruktur verändern. Der Ablauf für ein neues Deployment:

1. Code auf `main` pushen → Plan läuft automatisch
2. Plan in GitHub Actions prüfen
3. `Actions → Deploy to GCP → Run workflow → apply=true`
4. Apply läuft, Kubernetes wird aktualisiert

---

## prevent_destroy — Schutz kritischer Ressourcen

`terraform destroy` (zum Kostensparen zwischen Sessions) würde ohne Schutz alle Ressourcen löschen — inklusive der CI/CD Infrastruktur. Mit `prevent_destroy` bleiben kritische Ressourcen erhalten:

| Ressource | `prevent_destroy` | Begründung |
|-----------|-------------------|------------|
| WIF Pool + Provider | ✅ | Für CI/CD dauerhaft notwendig |
| CI/CD Service Account | ✅ | GitHub Secrets referenzieren ihn |
| Artifact Registry | ✅ | Images sollen erhalten bleiben |
| GCP Service Accounts (api-gateway, worker) | ✅ | IAM-Bindings dauerhaft |
| HMAC Keys | ✅ | Kubernetes Secret referenziert sie |
| GCS Buckets | ✅ | Videos sollen nicht verloren gehen |
| GKE Cluster | ❌ | Wird zum Kostensparen runtergefahren |

`terraform destroy` schlägt bei geschützten Ressourcen fehl. Um sie doch zu löschen: `prevent_destroy` aus den `.tf` Dateien entfernen, `terraform apply` ausführen, dann `terraform destroy`.

---

## Terraform State

Der Terraform State liegt im GCS Bucket `k8s-transcoding-tfstate` — nicht lokal. Das hat zwei Vorteile:

- State geht nicht verloren wenn der lokale Rechner wechselt
- GitHub Actions und lokale Terraform-Ausführungen nutzen denselben State

Der State Bucket ist bewusst **nicht** in Terraform verwaltet (Henne-Ei-Problem) und wird einmalig manuell erstellt:

```fish
gcloud storage buckets create gs://k8s-transcoding-tfstate \
  --project k8s-transcoding-plattform \
  --location us-central1
```

---

**Nächstes Dokument:** [CI/CD Challenges](../06-lessons-learned/cicd-challenges.md)
