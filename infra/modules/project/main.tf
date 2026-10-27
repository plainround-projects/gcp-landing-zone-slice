resource "google_project" "this" {
  name       = var.name
  project_id = var.project_id
  folder_id  = var.folder_id
  labels     = var.labels

  billing_account = var.billing_account

  # No default network: the shared VPC is the only network a service project uses.
  auto_create_network = false
  deletion_policy     = var.deletion_policy
}

# Every API, admin and data access, is audited in every project: the proofs and the dry-run reviews read these logs.
resource "google_project_iam_audit_config" "all_services" {
  count = var.audit_all_services ? 1 : 0

  project = google_project.this.project_id
  service = "allServices"

  audit_log_config {
    log_type = "ADMIN_READ"
  }

  audit_log_config {
    log_type = "DATA_READ"
  }

  audit_log_config {
    log_type = "DATA_WRITE"
  }
}

resource "google_project_service" "enabled" {
  for_each = toset(var.services)

  project            = google_project.this.project_id
  service            = each.value
  disable_on_destroy = false
}
