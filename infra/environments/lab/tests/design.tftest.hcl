# The environment builds exactly what design/landing-zone.yaml and policies/org-policies.yaml describe.
mock_provider "google" {}

variables {
  org_id           = "123456789012"
  billing_account  = "AAAAAA-BBBBBB-CCCCCC"
  quota_project_id = "lz-bootstrap-ab12cd"
  name_suffix      = "ab12cd"
  operator_member  = "user:operator@example-lab.org"
}

run "the_four_projects_of_the_design_get_the_suffix" {
  command = plan

  assert {
    condition     = jsonencode(output.project_ids) == jsonencode({ "prod-data" = "prod-data-ab12cd", "prod-app" = "prod-app-ab12cd", "dev-app" = "dev-app-ab12cd", "net-host" = "net-host-ab12cd" })
    error_message = "Project ids are the design names plus the suffix."
  }
}

run "the_four_lesson_policies_are_managed_at_the_organization_in_dry_run_mode_first" {
  command = plan

  assert {
    condition     = output.policy_constraints == tolist(["compute.vmExternalIpAccess@organization", "gcp.resourceLocations@organization", "iam.disableServiceAccountKeyCreation@organization", "storage.uniformBucketLevelAccess@organization"])
    error_message = "Four policies on the organization."
  }

  assert {
    condition     = output.policy_mode == "dry_run" && output.perimeter.mode == "dry_run"
    error_message = "Both start in dry run."
  }
}

run "the_shared_vpc_has_the_lessons_two_subnets" {
  command = plan

  assert {
    condition     = jsonencode(output.subnet_cidrs) == jsonencode({ "subnet-prod" = "10.50.0.0/24", "subnet-dev" = "10.60.0.0/24" })
    error_message = "subnet-prod 10.50.0.0/24 and subnet-dev 10.60.0.0/24."
  }
}

run "enforcing_is_a_variable_change_not_a_code_change" {
  command = plan

  variables {
    policy_mode    = "enforced"
    perimeter_mode = "enforced"
  }

  assert {
    condition     = output.policy_mode == "enforced" && output.perimeter.mode == "enforced"
    error_message = "Both flip together."
  }
}

run "the_bucket_name_is_the_lessons_name_plus_the_suffix" {
  command = plan

  assert {
    condition     = output.sensitive_bucket == "prod-data-sensitive-ab12cd"
    error_message = "prod-data-sensitive plus the suffix."
  }
}

run "a_bad_suffix_is_rejected" {
  command = plan

  variables {
    name_suffix = "Bad Suffix"
  }

  expect_failures = [var.name_suffix]
}

run "a_non_numeric_org_id_is_rejected" {
  command = plan

  variables {
    org_id = "example-lab.org"
  }

  expect_failures = [var.org_id]
}
