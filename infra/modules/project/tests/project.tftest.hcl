mock_provider "google" {}

variables {
  name            = "dev-app"
  project_id      = "dev-app-ab12cd"
  folder_id       = "123456789012"
  billing_account = "AAAAAA-BBBBBB-CCCCCC"
  services        = ["compute.googleapis.com"]
  labels          = { environment = "lab" }
}

run "the_project_has_no_default_network_and_carries_its_labels" {
  command = plan

  assert {
    condition     = google_project.this.auto_create_network == false && google_project.this.labels["environment"] == "lab"
    error_message = "No default network, labels set."
  }
}

run "every_service_is_audited_by_default" {
  command = plan

  assert {
    condition     = length(google_project_iam_audit_config.all_services) == 1 && google_project_iam_audit_config.all_services[0].service == "allServices"
    error_message = "Audit logs for all services."
  }
}

run "listed_apis_are_enabled" {
  command = plan

  assert {
    condition     = length(google_project_service.enabled) == 1
    error_message = "One API enabled."
  }
}

run "a_bad_project_id_is_rejected" {
  command = plan

  variables {
    project_id = "Dev_App"
  }

  expect_failures = [var.project_id]
}
