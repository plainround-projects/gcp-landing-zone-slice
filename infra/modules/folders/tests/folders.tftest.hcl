mock_provider "google" {}

variables {
  parent = "organizations/123456789012"
  names  = ["production", "non-production", "shared"]
}

run "one_folder_per_name_under_the_parent" {
  command = plan

  assert {
    condition     = length(google_folder.this) == 3 && alltrue([for f in google_folder.this : f.parent == "organizations/123456789012"])
    error_message = "Three folders under the organization."
  }
}

run "a_bad_parent_is_rejected" {
  command = plan

  variables {
    parent = "projects/x"
  }

  expect_failures = [var.parent]
}

run "duplicate_names_are_rejected" {
  command = plan

  variables {
    names = ["a", "a"]
  }

  expect_failures = [var.names]
}
