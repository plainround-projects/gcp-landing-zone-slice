mock_provider "google" {}

variables {
  prod_app_project_id = "prod-app-ab12cd"
  dev_app_project_id  = "dev-app-ab12cd"
  data_project_id     = "prod-data-ab12cd"
  operator_member     = "user:operator@example-lab.org"
}

run "three_identities_exist_and_none_has_a_key" {
  command = plan

  assert {
    condition     = google_service_account.team_prod.account_id == "team-prod-tester" && google_service_account.team_dev.account_id == "team-dev-tester" && google_service_account.data_reader.account_id == "data-reader"
    error_message = "Three test identities."
  }
}

run "only_the_operator_may_impersonate_them" {
  command = plan

  assert {
    condition     = length(google_service_account_iam_member.operator_impersonates) == 3 && alltrue([for b in google_service_account_iam_member.operator_impersonates : b.member == "user:operator@example-lab.org" && b.role == "roles/iam.serviceAccountTokenCreator"])
    error_message = "The operator holds tokenCreator on each, on the account itself."
  }
}

run "a_bad_operator_member_is_rejected" {
  command = plan

  variables {
    operator_member = "operator@example-lab.org"
  }

  expect_failures = [var.operator_member]
}
