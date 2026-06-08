# -------------------------------------------------------------------
# Object Storage Buckets
# S3-kompatibel — boto3 funktioniert ohne Code-Änderungen
# -------------------------------------------------------------------

resource "stackit_objectstorage_bucket" "uploads" {
  project_id = var.project_id
  name       = var.uploads_bucket_name
}

resource "stackit_objectstorage_bucket" "outputs" {
  project_id = var.project_id
  name       = var.outputs_bucket_name
}

# -------------------------------------------------------------------
# Object Storage Credentials
# Werden als Kubernetes Secret im Cluster hinterlegt
# (kein Workload Identity auf StackIT → Credentials nötig)
# -------------------------------------------------------------------

resource "stackit_objectstorage_credentials_group" "transcoding" {
  project_id = var.project_id
  name       = "transcoding-credentials"
}

resource "stackit_objectstorage_credential" "transcoding" {
  project_id           = var.project_id
  credentials_group_id = stackit_objectstorage_credentials_group.transcoding.credentials_group_id
  expiration_timestamp = "2027-01-01T00:00:00Z"
}

