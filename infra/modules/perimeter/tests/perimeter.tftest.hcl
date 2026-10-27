mock_provider "google" {}

variables {
  organization        = "organizations/123456789012"
  access_policy_id    = "987654321"
  name                = "sensitive_data"
  title               = "Sensitive data"
  project_numbers     = ["111111111111"]
  restricted_services = ["storage.googleapis.com", "bigquery.googleapis.com"]
  access_levels       = { office = ["203.0.113.0/24"] }
  access_level_names  = ["office"]
}

run "dry_run_writes_the_dry_run_spec_and_no_enforced_status" {
  command = plan

  assert {
    condition     = google_access_context_manager_service_perimeter.this.use_explicit_dry_run_spec && length(google_access_context_manager_service_perimeter.this.spec) == 1 && length(google_access_context_manager_service_perimeter.this.status) == 0
    error_message = "Dry run: spec only."
  }
}

run "enforced_writes_the_status_too" {
  command = plan

  variables {
    mode = "enforced"
  }

  assert {
    condition     = length(google_access_context_manager_service_perimeter.this.status) == 1 && length(google_access_context_manager_service_perimeter.this.spec) == 1
    error_message = "Enforced: status and spec."
  }
}

run "the_perimeter_surrounds_only_the_listed_projects_and_restricts_the_listed_services" {
  command = plan

  assert {
    condition     = google_access_context_manager_service_perimeter.this.spec[0].resources == toset(["projects/111111111111"]) && length(google_access_context_manager_service_perimeter.this.spec[0].restricted_services) == 2
    error_message = "One project, two services."
  }
}

run "an_existing_access_policy_is_reused_not_created" {
  command = plan

  assert {
    condition     = length(google_access_context_manager_access_policy.this) == 0 && output.access_policy_id == "987654321"
    error_message = "Reuse the given policy."
  }
}

run "without_an_access_policy_id_one_is_created" {
  command = plan

  variables {
    access_policy_id = ""
  }

  assert {
    condition     = length(google_access_context_manager_access_policy.this) == 1
    error_message = "Create the policy."
  }
}

run "a_perimeter_around_nothing_is_rejected" {
  command = plan

  variables {
    project_numbers = []
  }

  expect_failures = [var.project_numbers]
}
