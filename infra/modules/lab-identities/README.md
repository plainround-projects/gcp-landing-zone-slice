# lab-identities

Three service accounts without keys that stand in for a team-prod member, a team-dev member and a principal who can read the sensitive data; the operator may impersonate them.

Used for: Steps 3 and 5 (prove the subnet rules and attack as a principal with valid read access).

## Inputs

| Name | Description | Type | Default |
| --- | --- | --- | --- |
| `prod_app_project_id` | Project id of prod-app. | `string` | required |
| `dev_app_project_id` | Project id of dev-app. | `string` | required |
| `data_project_id` | Project id of prod-data. | `string` | required |
| `operator_member` | Who may impersonate the test identities, for example user:you@example-lab.org. | `string` | required |

## Outputs

| Name | Description |
| --- | --- |
| `team_prod_member` | IAM member of the team-prod test identity. |
| `team_dev_member` | IAM member of the team-dev test identity. |
| `data_reader_member` | IAM member of the data reader. |
| `emails` | Emails of the three test identities. |

## Example

See `infra/environments/lab/main.tf`, which composes this module.

## Tests

yes (`tests/*.tftest.hcl`, mock provider). Run `make test-terraform` from the repository root.
