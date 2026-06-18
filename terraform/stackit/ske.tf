# -------------------------------------------------------------------
# SKE Cluster (StackIT Kubernetes Engine)
# Analog zu GKE Autopilot — managed Kubernetes
# -------------------------------------------------------------------

resource "stackit_ske_cluster" "main" {
  project_id             = var.project_id
  name                   = var.cluster_name
  kubernetes_version_min = "1.33" # TODO: Ändern auf neueste Version, da deprecated

  node_pools = [
    {
      name         = "tc-pool"
      machine_type = "g1a.2d"   # 2 vCPU, 8 GB RAM — ausreichend für API Gateway
      minimum      = 1
      maximum      = 3        # Automatische Skalierung bis 3 Nodes
      os_name      = "flatcar"
      os_version_min = "4459.2.4" # TODO: Ändern auf neueste Version, da deprecated
      availability_zones = ["eu01-1"]
    }
  ]

  maintenance = {
    enable_kubernetes_version_updates    = true
    enable_machine_image_version_updates = true
    start = "01:00:00+00:00"
    end   = "03:00:00+00:00"
  }
}
