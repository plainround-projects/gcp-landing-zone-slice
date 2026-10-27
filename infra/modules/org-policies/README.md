# org-policies

Organization policies from the policy file. Every policy gets a dry-run spec; the enforced spec is written only when `mode = "enforced"`, so a change is logged before it blocks anything.

Used for: Step 2 (organization policies, dry run first).

## Inputs

| Name | Description | Type | Default |
| --- | --- | --- | --- |
| `organization` | organizations/ID, the parent of organization-level policies. | `string` | required |
| `folder_parents` | Folder name => folders/ID, for policies set at folder level. | `map(string)` | `{}` |
| `mode` | dry_run writes only the dry-run spec (violations are logged, nothing is blocked); enforced also writes the real spec. | `string` | `"dry_run"` |
| `policies` | The policy entries of policies/org-policies.yaml. | `list(object({ constraint = string kind = string enforce = optional(bool, false) allowed_values = optional(list(string), []) deny_all = optional(bool, false) folder = optional(string) }))` | required |

## Outputs

| Name | Description |
| --- | --- |
| `constraints` | Constraint@level of every policy managed here. |
| `mode` | dry_run or enforced. |

## Example

See `infra/environments/sandbox/main.tf`, which composes this module.

## Tests

yes (`tests/*.tftest.hcl`, mock provider). Run `make test-terraform` from the repository root.
