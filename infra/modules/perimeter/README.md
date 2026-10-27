# perimeter

An access policy (or an existing one), access levels from address ranges, and a VPC Service Controls perimeter whose dry-run configuration (`spec`) is always written and whose enforced configuration (`status`) is written only when `mode = "enforced"`.

Used for: Steps 4 and 5 (dry-run the perimeter, enforce and attack).

## Inputs

| Name | Description | Type | Default |
| --- | --- | --- | --- |
| `organization` | organizations/ID, the parent of the access policy. | `string` | required |
| `access_policy_id` | Id (the number) of the organization's existing access policy. Empty creates one. | `string` | `""` |
| `name` | Perimeter name: letters, digits and underscores. | `string` | required |
| `title` | Human-readable title. | `string` | required |
| `project_numbers` | Numbers of the projects inside the perimeter. | `list(string)` | required |
| `restricted_services` | Services the perimeter restricts, for example storage.googleapis.com. | `list(string)` | required |
| `access_levels` | Access level name => IP ranges whose callers count as trusted. | `map(list(string))` | `{}` |
| `access_level_names` | Names of the access levels the perimeter accepts (a subset of access_levels). | `list(string)` | `[]` |
| `mode` | dry_run logs what the perimeter would block; enforced blocks it. Always run dry_run first. | `string` | `"dry_run"` |

## Outputs

| Name | Description |
| --- | --- |
| `access_policy_id` | Id of the access policy the perimeter belongs to. |
| `perimeter_name` | Full resource name of the perimeter. |
| `mode` | dry_run or enforced. |

## Example

See `infra/environments/sandbox/main.tf`, which composes this module.

## Tests

yes (`tests/*.tftest.hcl`, mock provider). Run `make test-terraform` from the repository root.
