variable "project_id" {
  description = "StackIT Project ID"
  type        = string
}

variable "region" {
  description = "StackIT region"
  type        = string
  default     = "eu01"
}

variable "cluster_name" {
  description = "SKE cluster name"
  type        = string
  default     = "video-transcoding"
}

variable "namespace" {
  description = "Kubernetes namespace"
  type        = string
  default     = "video-transcoding"
}

variable "uploads_bucket_name" {
  description = "Object Storage bucket name for input videos"
  type        = string
}

variable "outputs_bucket_name" {
  description = "Object Storage bucket name for transcoded videos"
  type        = string
}

