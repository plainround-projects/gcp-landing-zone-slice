mock_provider "google" {}

variables {
  organization = "organizations/123456789012"
  policies = [
    { constraint = "iam.disableServiceAccountKeyCreation", kind = "boolean", enforce = true },
    { constraint = "gcp.resourceLocations", kind = "list", allowed_values = ["in:eu-locations"] },
    { constraint = "compute.vmExternalIpAccess", kind = "list", deny_all = true },
  ]
}

run "in_dry_run_mode_only_the_dry_run_spec_exists" {
  command = plan

  assert {
    condition     = alltrue([for p in google_org_policy_policy.this : length(p.spec) == 0 && length(p.dry_run_spec) == 1])
    error_message = "Dry run writes dry_run_spec only."
  }
}

run "in_enforced_mode_both_specs_exist" {
  command = plan

  variables {
    mode = "enforced"
  }

  assert {
    condition     = alltrue([for p in google_org_policy_policy.this : length(p.spec) == 1 && length(p.dry_run_spec) == 1])
    error_message = "Enforced writes spec and dry_run_spec."
  }
}

run "each_policy_lands_on_the_organization" {
  command = plan

  assert {
    condition     = alltrue([for p in google_org_policy_policy.this : p.parent == "organizations/123456789012"]) && length(google_org_policy_policy.this) == 3
    error_message = "Three policies on the organization."
  }
}

run "a_folder_policy_lands_on_its_folder" {
  command = plan

  variables {
    folder_parents = { production = "folders/555" }
    policies       = [{ constraint = "compute.vmExternalIpAccess", kind = "list", deny_all = true, folder = "production" }]
  }

  assert {
    condition     = google_org_policy_policy.this["compute.vmExternalIpAccess@production"].parent == "folders/555"
    error_message = "A folder policy is set on the folder."
  }
}

run "a_list_policy_with_both_allowed_values_and_deny_all_is_rejected" {
  command = plan

  variables {
    policies = [{ constraint = "x.y", kind = "list", allowed_values = ["a"], deny_all = true }]
  }

  expect_failures = [var.policies]
}

run "an_unknown_mode_is_rejected" {
  command = plan

  variables {
    mode = "yolo"
  }

  expect_failures = [var.mode]
}
