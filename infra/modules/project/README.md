# project

A project in a folder with billing, no default network, labels and its APIs.

Used for: Steps 1 and 3 (the four projects).

## Inputs

| Name | Description | Type | Default |
| --- | --- | --- | --- |
| `name` | Display name, also the lesson's project name. | `string` | required |
| `project_id` | Globally unique project id (6-30 characters). | `string` | required |
| `folder_id` | Folder the project lives in (the number only). | `string` | required |
| `billing_account` | Billing account id. | `string` | required |
| `services` | APIs to enable. | `list(string)` | `[]` |
| `labels` | Labels for the project. | `map(string)` | `{}` |
| `deletion_policy` | PREVENT, ABANDON or DELETE. DELETE in a lab so terraform destroy schedules the project for deletion. | `string` | `"DELETE"` |

## Outputs

| Name | Description |
| --- | --- |
| `project_id` | Project id. |
| `number` | Project number. |

## Example

See `infra/environments/sandbox/main.tf`, which composes this module.

## Tests

yes (`tests/*.tftest.hcl`, mock provider). Run `make test-terraform` from the repository root.
