resource "google_compute_shared_vpc_host_project" "host" {
  project = var.host_project_id
}

resource "google_compute_shared_vpc_service_project" "service" {
  for_each = var.service_projects

  host_project    = google_compute_shared_vpc_host_project.host.project
  service_project = each.value
}

resource "google_compute_network" "this" {
  project                 = var.host_project_id
  name                    = var.network_name
  auto_create_subnetworks = false

  depends_on = [google_compute_shared_vpc_host_project.host]
}

resource "google_compute_subnetwork" "this" {
  for_each = var.subnets

  project                  = var.host_project_id
  name                     = each.key
  region                   = var.region
  network                  = google_compute_network.this.id
  ip_cidr_range            = each.value.cidr
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# Each team may use its own subnet and no other: networkUser is granted on the subnet, never on the host project.
resource "google_compute_subnetwork_iam_member" "network_user" {
  for_each = local.subnet_users

  project    = var.host_project_id
  region     = var.region
  subnetwork = google_compute_subnetwork.this[each.value.subnet].name
  role       = "roles/compute.networkUser"
  member     = each.value.member
}

locals {
  # Key: subnet plus position, so the keys are known at plan time even when a member is not.
  subnet_users = merge([
    for subnet, config in var.subnets : {
      for index, member in config.users : "${subnet}/${index}" => { subnet = subnet, member = member }
    }
  ]...)
}

# Everything not explicitly allowed is denied, and the denials are logged.
resource "google_compute_firewall" "deny_all_ingress" {
  project   = var.host_project_id
  name      = "${var.network_name}-deny-all-ingress"
  network   = google_compute_network.this.id
  direction = "INGRESS"
  priority  = 65534

  source_ranges = ["0.0.0.0/0"]

  deny {
    protocol = "all"
  }

  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}
