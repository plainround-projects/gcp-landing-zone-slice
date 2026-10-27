# 1. The design and the policies are data that Terraform and a tool both read

Status: accepted, 2026-10-27

## Context

The lesson keeps the organization policies "in one file, `org-policies.yaml`, so they are code", asks for a reason and a blocked request for each, and asks the owner to show which control stopped each attempt. If the Terraform, the documentation and any checks each held their own copy of the folders, subnets and policies, they would drift.

## Decision

`design/landing-zone.yaml` (folders, projects, shared VPC, perimeter, access levels, the sensitive object) and `policies/org-policies.yaml` (constraint, how it is set, reason, the request it blocks) are the single source. `infra/environments/lab` reads them with `yamldecode`. The `landing-zone` tool reads the same files: `check` verifies the design is consistent and every policy has a reason and a blocked request, `explain` prints the table step 1 asks for, `render-policies` writes the YAML that `gcloud org-policies set-policy` takes, and `simulate` evaluates `design/scenarios.yaml` against them.

## Consequences

- Changing a CIDR or adding a policy is one edit, reviewed once.
- A test compares the literals in the Terraform tests with the design file, so the two cannot disagree silently.
- Terraform sees only what the YAML carries. Values that must not live in the repository (organization id, billing account, suffix, the operator) stay variables.
