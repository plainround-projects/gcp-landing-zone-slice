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
