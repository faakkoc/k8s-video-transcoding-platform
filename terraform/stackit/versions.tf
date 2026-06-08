terraform {
  required_version = ">= 1.0"

  required_providers {
    stackit = {
      source  = "stackitcloud/stackit"
      version = "~> 0.96.0"
    }
  }

  # Remote State in StackIT Object Storage (S3-kompatibel)
  # Credentials werden via Umgebungsvariablen gesetzt:
  #   export AWS_ACCESS_KEY_ID=<state-bucket-access-key>
  #   export AWS_SECRET_ACCESS_KEY=<state-bucket-secret-key>
  backend "s3" {
    bucket   = "k8s-transcoding-tfstate-stackit"
    key      = "terraform/state"
    region   = "eu01"
    endpoints = {
      s3 = "https://object.storage.eu01.onstackit.cloud"
    }
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_s3_checksum            = true
    skip_requesting_account_id  = true
  }
}

