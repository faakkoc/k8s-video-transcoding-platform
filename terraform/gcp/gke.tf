module "gke" {
  source  = "terraform-google-modules/kubernetes-engine/google//modules/beta-autopilot-public-cluster"
  version = "~> 36.0"

  project_id = var.project_id
  name       = var.cluster_name
  region     = var.region

  network           = "default"
  subnetwork        = "default"
  ip_range_pods     = ""
  ip_range_services = ""

  release_channel     = "REGULAR"
  deletion_protection = false

  depends_on = [google_project_service.apis]
}
