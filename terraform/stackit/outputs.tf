output "cluster_name" {
  description = "SKE cluster name"
  value       = stackit_ske_cluster.main.name
}

output "uploads_bucket" {
  description = "Object Storage bucket for input videos"
  value       = stackit_objectstorage_bucket.uploads.name
}

output "outputs_bucket" {
  description = "Object Storage bucket for transcoded videos"
  value       = stackit_objectstorage_bucket.outputs.name
}

output "s3_endpoint" {
  description = "S3-compatible endpoint for StackIT Object Storage"
  value       = "https://object.storage.eu01.onstackit.cloud"
}

output "object_storage_access_key" {
  description = "Access Key ID for Object Storage (use as S3_ACCESS_KEY)"
  value       = stackit_objectstorage_credential.transcoding.access_key
  sensitive   = true
}

output "object_storage_secret_key" {
  description = "Secret Access Key for Object Storage (use as S3_SECRET_KEY)"
  value       = stackit_objectstorage_credential.transcoding.secret_access_key
  sensitive   = true
}

output "kubeconfig_command" {
  description = "Command to configure kubectl for this cluster"
  value       = "stackit ske kubeconfig create --project-id ${var.project_id} --cluster-name ${var.cluster_name}"
}

