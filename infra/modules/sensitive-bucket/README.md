# sensitive-bucket

A private, uniform-access, versioned bucket in an EU location, readable by the listed members only.

Used for: Step 5 (the data the perimeter protects).

## Inputs

| Name | Description | Type | Default |
| --- | --- | --- | --- |
| `project_id` | Project that owns the bucket. | `string` | required |
| `name` | Globally unique bucket name. | `string` | required |
| `location` | Bucket location; the organization policy only allows EU locations. | `string` | required |
| `viewer_members` | Members that may read objects in this bucket, keyed by a fixed label. | `map(string)` | `{}` |
| `force_destroy` | Delete the bucket even when it holds objects. True only for a lab. | `bool` | `false` |
| `labels` | Labels for the bucket. | `map(string)` | `{}` |

## Outputs

| Name | Description |
| --- | --- |
| `name` | Bucket name. |
| `viewer_members` | Members granted objectViewer. |

## Example

See `infra/environments/sandbox/main.tf`, which composes this module.

## Tests

yes (`tests/*.tftest.hcl`, mock provider). Run `make test-terraform` from the repository root.
