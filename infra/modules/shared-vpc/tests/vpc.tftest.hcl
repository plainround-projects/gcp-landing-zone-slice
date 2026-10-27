mock_provider "google" {}

variables {
  host_project_id  = "net-host-ab12cd"
  service_projects = { prod-app = "prod-app-ab12cd", dev-app = "dev-app-ab12cd" }
  network_name     = "shared-net"
  region           = "europe-west1"
  subnets = {
    subnet-prod = { cidr = "10.50.0.0/24", users = ["group:team-prod@example-lab.org"] }
    subnet-dev  = { cidr = "10.60.0.0/24", users = ["group:team-dev@example-lab.org"] }
  }
}

run "two_service_projects_are_attached_to_the_host" {
  command = plan

  assert {
    condition     = length(google_compute_shared_vpc_service_project.service) == 2
    error_message = "Both service projects attach to the host."
  }
}

run "each_team_is_bound_to_its_own_subnet_only" {
  command = plan

  assert {
    condition     = google_compute_subnetwork_iam_member.network_user["subnet-prod/0"].subnetwork == "subnet-prod" && google_compute_subnetwork_iam_member.network_user["subnet-prod/0"].member == "group:team-prod@example-lab.org"
    error_message = "team-prod is bound to subnet-prod."
  }

  assert {
    condition     = length(google_compute_subnetwork_iam_member.network_user) == 2 && alltrue([for b in google_compute_subnetwork_iam_member.network_user : b.role == "roles/compute.networkUser"])
    error_message = "One networkUser binding per team, on the subnet, nothing on the project."
  }
}

run "subnets_use_private_google_access_and_flow_logs" {
  command = plan

  assert {
    condition     = alltrue([for s in google_compute_subnetwork.this : s.private_ip_google_access && length(s.log_config) == 1])
    error_message = "Private Google Access and flow logs on every subnet."
  }
}

run "the_network_is_custom_mode_with_an_explicit_deny" {
  command = plan

  assert {
    condition     = google_compute_network.this.auto_create_subnetworks == false && google_compute_firewall.deny_all_ingress.priority == 65534
    error_message = "Custom mode and a deny-all ingress rule."
  }
}

run "a_subnet_nobody_may_use_is_rejected" {
  command = plan

  variables {
    subnets = { subnet-x = { cidr = "10.70.0.0/24", users = [] } }
  }

  expect_failures = [var.subnets]
}
