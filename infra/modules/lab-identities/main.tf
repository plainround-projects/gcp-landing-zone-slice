# Test identities for the lesson's proofs. They hold no key. Delete them with the lab; real teams use groups.
# The operator (you) impersonates them, so every proof runs as the identity under test and not as you.

resource "google_service_account" "team_prod" {
  project      = var.prod_app_project_id
  account_id   = "team-prod-tester"
  display_name = "Stands in for a member of team-prod"
}

resource "google_service_account" "team_dev" {
  project      = var.dev_app_project_id
  account_id   = "team-dev-tester"
  display_name = "Stands in for a member of team-dev"
}

resource "google_service_account" "data_reader" {
  project      = var.data_project_id
  account_id   = "data-reader"
  display_name = "Can read the sensitive bucket; used to attack the perimeter"
}

# A team member may create VMs in its own service project. The subnet rights come from the shared-vpc module.
resource "google_project_iam_member" "team_prod_instances" {
  project = var.prod_app_project_id
  role    = "roles/compute.instanceAdmin.v1"
  member  = "serviceAccount:${google_service_account.team_prod.email}"
}

resource "google_project_iam_member" "team_dev_instances" {
  project = var.dev_app_project_id
  role    = "roles/compute.instanceAdmin.v1"
  member  = "serviceAccount:${google_service_account.team_dev.email}"
}

resource "google_service_account_iam_member" "operator_impersonates" {
  for_each = {
    team_prod   = google_service_account.team_prod.name
    team_dev    = google_service_account.team_dev.name
    data_reader = google_service_account.data_reader.name
  }

  service_account_id = each.value
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = var.operator_member
}
