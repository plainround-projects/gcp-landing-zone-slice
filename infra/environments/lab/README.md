# lab environment

The composition for the landing-zone slice: folders, projects, organization policies, the shared VPC, the sensitive bucket, the test identities and the perimeter, built from `design/landing-zone.yaml` and `policies/org-policies.yaml`. Every module is in `../../modules`.

## Variables

See `variables.tf`; `lab.tfvars.example` shows every value with placeholders. `scripts/deploy.sh` writes the real `lab.tfvars` from `.env` (git-ignored). `policy_mode` and `perimeter_mode` both default to `dry_run`; `scripts/enforce.sh` flips them. `quota_project_id` is a project that already exists (`scripts/bootstrap.sh` creates it).

## Validate without credentials

```bash
cd infra/environments/lab
terraform init -backend=false
terraform validate
GOOGLE_OAUTH_ACCESS_TOKEN=offline-placeholder terraform plan -var-file=lab.tfvars.example   # 50 resources to add, no API call
terraform test                                                                             # the design, the modes, the names
```

The offline plan works because nothing in the configuration reads from Google Cloud: the design comes from the YAML files, and no data source is used.

## Enforcing and tearing down

Enforcing the perimeter also stops Terraform, run from an address outside the `office` access level, from reading the bucket. That is the perimeter working. After enforcement use `terraform apply -refresh=false`, or set `office_ip_subnetworks` to your address first. `scripts/teardown.sh` relaxes the perimeter with a targeted `-refresh=false` apply, waits, then destroys.

## Outputs

`project_ids`, `project_numbers`, `folders`, `policy_constraints`, `policy_mode`, `subnet_cidrs`, `perimeter`, `access_policy_id`, `sensitive_bucket`, `test_identities`.

## State

Local. For shared use copy `backend.tf.example` to `backend.tf`, create the bucket (versioning on) and run `terraform init -migrate-state`.
