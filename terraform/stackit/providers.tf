# StackIT Provider Authentifizierung via Service Account Key (JSON-Datei)
# Die JSON-Datei wird über die Umgebungsvariable STACKIT_SERVICE_ACCOUNT_KEY_PATH gesetzt
# Kein Workload Identity auf StackIT — Service Account Key ist der Standard-Weg

provider "stackit" {
  default_region = var.region
  # service_account_key_path wird via STACKIT_SERVICE_ACCOUNT_KEY_PATH ENV gesetzt
  # (nicht hardcoded — JSON-Datei bleibt lokal und wird nicht ins Repo eingecheckt)
}

