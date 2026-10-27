# 2. Dry run is the default for every policy and the perimeter

Status: accepted, 2026-10-27

## Context

An organization policy refuses creations that were allowed yesterday, and a VPC Service Controls perimeter refuses calls that IAM allows. The lesson says every change goes through dry-run mode first, "as a real platform team would do".

## Decision

`modules/org-policies` always writes `dry_run_spec` and writes `spec` only when `mode = "enforced"`. `modules/perimeter` sets `use_explicit_dry_run_spec = true`, always writes `spec` (the dry-run configuration) and writes `status` (the enforced configuration) only when `mode = "enforced"`. The environment's `policy_mode` and `perimeter_mode` default to `dry_run`. `scripts/enforce.sh` asks for confirmation that the logs were read. Tests assert each default and each switch.

## Consequences

- The first `terraform apply` of a new organization blocks nothing.
- Enforcement is a one-variable change that appears in a pull request and in the plan.
- A dry-run perimeter only logs, so the proofs of steps 2 and 5 need the enforced mode and up to 30 minutes of propagation.
- After enforcement, Terraform from an address outside the access level cannot read the bucket; the teardown relaxes the perimeter first.
