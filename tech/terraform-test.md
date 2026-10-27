# `terraform test` (native Terraform tests)

## 1. What it is

`terraform test` is a built-in Terraform command that runs test files ending in `.tftest.hcl`. Each file contains `run` blocks. A run executes a plan (or an apply) with chosen variable values and then checks **assertions**: true/false conditions about the result. With a **mock provider** the whole thing runs offline: Terraform pretends to be Google instead of calling it. The feature needs Terraform 1.7 or newer (mock providers) and is used here with 1.17.

## 2. Why this repository uses it

The "no organization needed" rule: the wiring (which policy is written in which mode, which subnet which group may use, what the perimeter surrounds) can be tested on a laptop. A test fails if dry run stops being the default, if a bad value is accepted, if the design file and the Terraform disagree, or if enforcing stops being just a variable.

## 3. Where it appears

| Path | What it checks |
| --- | --- |
| `infra/modules/folders/tests/folders.tftest.hcl` | One folder per name under the parent; a bad parent and duplicate names are rejected (3 runs). |
| `infra/modules/project/tests/project.tftest.hcl` | No default network and the labels set; audit logs on for every service; the listed APIs enabled; a bad project id rejected (4). |
| `infra/modules/org-policies/tests/policies.tftest.hcl` | Dry run writes `dry_run_spec` only; enforced writes both; the parent; contradictions rejected (6). |
| `infra/modules/lab-identities/tests/identities.tftest.hcl` | The three test identities exist; only the operator may impersonate them; a bad operator member is rejected (3). |
| `infra/modules/shared-vpc/tests/vpc.tftest.hcl` | Both service projects attach to the host; each team is bound to its own subnet only; private Google access and flow logs; a custom-mode network with an explicit deny rule; a subnet nobody may use is rejected (5). |
| `infra/modules/sensitive-bucket/tests/bucket.tftest.hcl` | The bucket is private, uniform and in the EU; only the listed member may read (2). |
| `infra/modules/perimeter/tests/perimeter.tftest.hcl` | Dry run writes `spec` only; enforced adds `status`; the perimeter surrounds only the listed projects; an existing access policy is reused; one is created otherwise; an empty perimeter is rejected (6). |
| `infra/environments/lab/tests/design.tftest.hcl` | The environment builds what the YAML files describe (7). |
| `Makefile` | `test-terraform` loops over every folder that has a `tests/` directory. |

## 4. How it works underneath

Terraform loads the module in the current folder, applies the test's `variables`, and for each `run` makes a plan (`command = plan`) in memory. `mock_provider "google" {}` replaces the real provider: computed attributes (emails, ids) get placeholder values, and nothing leaves your machine. Assertions are evaluated against resource attributes (inside a module under test) or module outputs (from an environment). `expect_failures = [var.name]` states that this run *should* fail validation of that variable; the run passes only if it does. A `variables { ... }` block inside a `run` overrides the file-level values for that run only.

Two limits shape the tests: placeholders are made up, so an assertion cannot compare a generated value to a literal; and a list in a variable differs from a tuple literal, so comparisons use `tolist(...)` or `jsonencode(...)`.

## 5. Walkthrough of this repository's use

`infra/modules/perimeter/tests/perimeter.tftest.hcl`

```hcl
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
```

- `mock_provider "google" {}`: use the fake provider.
- `variables { ... }` at the top gives defaults to every run.
- `run "name" { command = plan; assert { condition = ...; error_message = ... } }`: one test. `condition` is any expression; the run fails with the message if it is false.
- The first run states the lesson's central rule in a single line: dry run keeps `use_explicit_dry_run_spec`, writes exactly one `spec` and **no** `status`.

`infra/modules/perimeter/tests/perimeter.tftest.hcl`

```hcl
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
```

The `variables { mode = "enforced" }` inside the run flips only this test. Now `status` is written too.

A rejection test:

`infra/modules/perimeter/tests/perimeter.tftest.hcl`

```hcl
run "a_perimeter_around_nothing_is_rejected" {
  command = plan

  variables {
    project_numbers = []
  }

  expect_failures = [var.project_numbers]
}
```

`expect_failures = [var.project_numbers]` says this run must fail that variable's validation. If the module ever accepted an empty list, this test would fail.

A test over many resources:

`infra/modules/org-policies/tests/policies.tftest.hcl`

```hcl
run "in_dry_run_mode_only_the_dry_run_spec_exists" {
  command = plan

  assert {
    condition     = alltrue([for p in google_org_policy_policy.this : length(p.spec) == 0 && length(p.dry_run_spec) == 1])
    error_message = "Dry run writes dry_run_spec only."
  }
}
```

`alltrue([for p in google_org_policy_policy.this : ...])` checks every policy. `length(p.spec) == 0` means no enforced block exists.

The environment test checks that the build matches the design files:

`infra/environments/lab/tests/design.tftest.hcl`

```hcl
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
```

`infra/environments/lab/tests/design.tftest.hcl`

```hcl
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
```

- `output.project_ids` is compared through `jsonencode` so a map matches a literal map.
- `tolist([...])` makes the expected list the same type as the output.
- A second Python test (`test_the_terraform_test_literals_match_the_design_file`) checks that these literals still match `design/landing-zone.yaml`, so the YAML, the Terraform and the tests cannot drift apart.

`infra/environments/lab/tests/design.tftest.hcl`

```hcl
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
```

Both modes flip together with two variables, and no code changes.

## Every test file, run by run

Words used below. A **`run` block** is one test. `command = plan` makes the plan in memory and checks it; no resource is created anywhere. An **`assert` block** has a `condition` (must be true) and an `error_message` (shown if it is false). `&&` means "and". `==` compares. A `variables` block at the top of the file sets the inputs of every run; a `variables` block inside a run replaces some of them for that run only. `expect_failures = [var.name]` turns the run around: it passes only if that variable's `validation` rejects the value. A resource created with `for_each` is a map, so `length(resource.name)` counts the copies and `resource.name["key"]` picks one.

The perimeter and policy files were quoted above. The others:

### `infra/modules/folders/tests/folders.tftest.hcl`

`infra/modules/folders/tests/folders.tftest.hcl`

```hcl
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
```

- Run one: three folders exist and every folder's `parent` is the organization (`alltrue([for f in ... : ...])` checks each one).
- Run two: `parent = "projects/x"` is not an organization or folder, so the variable's validation must reject it.
- Run three: `names = ["a", "a"]` has a duplicate and must be rejected.

### `infra/modules/project/tests/project.tftest.hcl`

`infra/modules/project/tests/project.tftest.hcl`

```hcl
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
```

- Run one: `auto_create_network == false` (no default network) and the label `environment = "lab"` is set. `labels["environment"]` reads one entry of a map.
- Run two: the audit configuration exists once (`length(...) == 1`, it has `count`) and covers `allServices`. `[0]` picks the first (only) copy.
- Run three: the one API in `services` is enabled once.
- Run four: `"Dev_App"` has an uppercase letter and an underscore, so the id rule must reject it.

### `infra/modules/lab-identities/tests/identities.tftest.hcl`

`infra/modules/lab-identities/tests/identities.tftest.hcl`

```hcl
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
```

- Run one: the three accounts have the expected `account_id`s.
- Run two: there are exactly three impersonation bindings, and every one has the operator as member and `roles/iam.serviceAccountTokenCreator` as role.
- Run three: an operator written without the `user:` prefix is rejected.

### `infra/modules/shared-vpc/tests/vpc.tftest.hcl`

`infra/modules/shared-vpc/tests/vpc.tftest.hcl`

```hcl
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
```

- The top `variables` block uses the lesson's real values: two service projects and two subnets with one group each. `{ prod-app = "..." }` is an object written with `=`.
- Run one: both service projects are attached.
- Run two (two asserts): the binding keyed `subnet-prod/0` is on `subnet-prod` for the team-prod group, and there are exactly two bindings, each `roles/compute.networkUser`. Nothing is granted on the project.
- Run three: every subnet has Private Google Access on and one flow-log block.
- Run four: the network is custom mode (`auto_create_subnetworks == false`) and the deny rule's priority is 65534.
- Run five: a subnet with `users = []` must be rejected.

### `infra/modules/sensitive-bucket/tests/bucket.tftest.hcl`

`infra/modules/sensitive-bucket/tests/bucket.tftest.hcl`

```hcl
mock_provider "google" {}

variables {
  project_id     = "prod-data-ab12cd"
  name           = "prod-data-sensitive-ab12cd"
  location       = "europe-west1"
  viewer_members = { data_reader = "serviceAccount:data-reader@prod-data-ab12cd.iam.gserviceaccount.com" }
}

run "the_bucket_is_private_and_uniform_and_in_the_eu" {
  command = plan

  assert {
    condition     = google_storage_bucket.this.uniform_bucket_level_access && google_storage_bucket.this.public_access_prevention == "enforced" && lower(google_storage_bucket.this.location) == "europe-west1"
    error_message = "Private, uniform, EU."
  }
}

run "only_the_listed_member_may_read" {
  command = plan

  assert {
    condition     = length(google_storage_bucket_iam_member.viewer) == 1 && alltrue([for b in google_storage_bucket_iam_member.viewer : b.role == "roles/storage.objectViewer"])
    error_message = "One objectViewer binding."
  }
}
```

- Run one: the bucket has uniform access, public access prevention `"enforced"`, and its location (lower-cased with `lower(...)`, because Google normalizes case) is `europe-west1`.
- Run two: exactly one viewer binding exists and its role is `roles/storage.objectViewer`.

### `infra/modules/org-policies/tests/policies.tftest.hcl`, in full

`infra/modules/org-policies/tests/policies.tftest.hcl`

```hcl
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
```

- The top `variables` give three policies: a boolean (`enforce = true`), an allow list and a deny-all. Only the fields that differ from the defaults are written.
- Run one: in dry-run mode every policy has no `spec` and one `dry_run_spec`. Run two: with `mode = "enforced"` both exist.
- Run three: three policies, each on the organization. Run four: a policy with `folder = "production"` is keyed `compute.vmExternalIpAccess@production` and its parent is `folders/555`.
- Run five: a list policy with both `allowed_values` and `deny_all` is rejected. Run six: `mode = "yolo"` is rejected.

### `infra/modules/perimeter/tests/perimeter.tftest.hcl`, in full

`infra/modules/perimeter/tests/perimeter.tftest.hcl`

```hcl
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
```

- The first run checks `use_explicit_dry_run_spec` is on, that exactly one `spec` block exists, and that no `status` block exists.
- The third run checks `spec[0].resources == toset(["projects/111111111111"])` (a set of the one project, written with the `projects/` prefix) and two restricted services.
- The fourth and fifth runs prove the access policy is reused when an id is given (`length(...) == 0` copies are created, and the output equals the id) and created when it is empty.

### `infra/environments/lab/tests/design.tftest.hcl`, in full

`infra/environments/lab/tests/design.tftest.hcl`

```hcl
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
```

- It uses the **real** modules with the mock provider, so it tests the wiring: the design file, the locals and the modules together.
- Runs six and seven pass wrong inputs: `name_suffix = "Bad Suffix"` and `org_id = "example-lab.org"`; both must be rejected by the environment's own validations.
- Run five checks the bucket name is `prod-data-sensitive-ab12cd`: the design's bucket name plus the suffix.

## 6. Try it yourself

```bash
cd infra/modules/perimeter && terraform init -backend=false -input=false >/dev/null && terraform test
```
Expected: `Success! 6 passed, 0 failed.`

```bash
cd infra/environments/lab && terraform init -backend=false -input=false >/dev/null && terraform test
```
Expected: `Success! 7 passed, 0 failed.`

Break one on purpose: in `infra/modules/perimeter/main.tf` change `use_explicit_dry_run_spec = true` to `false`, run `terraform test` in that module, read which runs fail and why, then undo the change (`git checkout infra`).

```bash
make test-terraform
```
Expected: an `== infra/modules/...` heading and a `Success!` line for each of the seven modules and the environment: 3, 3, 6, 6, 4, 2, 5 and 7 runs passed (36 in total).

```bash
.venv/bin/python -m pytest tests/unit/test_infrastructure_policy.py -q -p no:cacheprovider -k "literals or constraints"
```
Expected: `2 passed`: the Python tests that read these Terraform test files and compare them with the YAML.

## 7. Mistakes people make

- **Comparing against generated mock values.** Assert on what you set (names, modes, counts), not on emails the mock invents.
- **Comparing a list with a tuple literal.** Use `tolist()`.
- **Forgetting `expect_failures`.** A validation error would fail the whole run.
- **Testing the provider, not your logic.** Assert your wiring (which mode writes which spec), not that Terraform works.
- **Believing a mock proves Google accepts it.** It does not; `scripts/prove.sh` does that against a real organization.

## 8. Check yourself

1. What does `mock_provider` do? *Replaces the real provider so nothing contacts the cloud.*
2. What does `expect_failures` mean? *The run passes only if that variable's validation fails.*
3. What does a `variables` block inside a `run` do? *Overrides the values for that run only.*
4. Which command runs all tests of a module? *`terraform test` in that folder.*
5. Why `tolist(...)`? *To make a literal the same type as the output.*

## 9. Further reading

- `terraform test`: <https://developer.hashicorp.com/terraform/language/tests>
- Mock providers: <https://developer.hashicorp.com/terraform/language/tests/mocking>
- Command reference: <https://developer.hashicorp.com/terraform/cli/commands/test>
