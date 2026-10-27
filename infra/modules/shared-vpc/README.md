# shared-vpc

A host project's shared VPC: custom-mode network, subnets with Private Google Access and flow logs, service projects attached, `networkUser` granted on each subnet to its own team only, and an explicit logged deny-all ingress rule.

Used for: Step 3 (share the network).

## Inputs

| Name | Description | Type | Default |
| --- | --- | --- | --- |
| `host_project_id` | Id of the host project that owns the network. | `string` | required |
| `service_projects` | Service projects attached to the host, keyed by a fixed label (the project name). | `map(string)` | required |
| `network_name` | Name of the shared VPC network. | `string` | required |
| `region` | Region of every subnet. | `string` | required |
| `subnets` | Subnets by name: the CIDR range and the IAM members that may use the subnet (roles/compute.networkUser). | `map(object({ cidr = string users = list(string) }))` | required |

## Outputs

| Name | Description |
| --- | --- |
| `network` | Self link of the shared network. |
| `subnets` | Subnet name => self link. |
| `subnet_cidrs` | Subnet name => CIDR range. |

## Example

See `infra/environments/lab/main.tf`, which composes this module.

## Tests

yes (`tests/*.tftest.hcl`, mock provider). Run `make test-terraform` from the repository root.
