# folders

Creates the folders under the organization.

Used for: Step 1 (the hierarchy).

## Inputs

| Name | Description | Type | Default |
| --- | --- | --- | --- |
| `parent` | Parent of every folder: organizations/ID or folders/ID. | `string` | required |
| `names` | Display names of the folders to create. | `list(string)` | required |
| `deletion_protection` | Refuse to delete the folders. False for a lab so the teardown works. | `bool` | `false` |

## Outputs

| Name | Description |
| --- | --- |
| `ids` | Folder name => folder id (the number only). |
| `names` | Folder name => resource name (folders/ID), the form parents take. |

## Example

See `infra/environments/lab/main.tf`, which composes this module.

## Tests

yes (`tests/*.tftest.hcl`, mock provider). Run `make test-terraform` from the repository root.
