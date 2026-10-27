# Shared VPC and VPC networking

## 1. What it is

A **VPC network** (Virtual Private Cloud) is a private network inside Google Cloud. It is global, and it holds **subnets**: each subnet is one address range (a CIDR range, see `ipaddress-and-cidr.md`) in one region. Machines get their addresses from a subnet. A **firewall rule** allows or denies traffic to or from machines.

**Shared VPC** lets one project, the **host project**, own the network while other projects, the **service projects**, put their machines in it. The network team controls addresses and rules in one place; each application team keeps its own project, billing and permissions. A project is either a host or a service project, never both, and a service project attaches to only one host. Who may use which subnet is an IAM question: the role `roles/compute.networkUser` on a **subnet** lets someone create machines in that subnet only.

## 2. Why this repository uses it

Step 3 of the lesson: give two teams their own subnet in one shared network, and make sure team A cannot create anything in team B's subnet. The host project `net-host` owns the network `shared-net`; `prod-app` and `dev-app` are its service projects; `subnet-prod` (`10.50.0.0/24`) belongs to team-prod and `subnet-dev` (`10.60.0.0/24`) to team-dev.

## 3. Where it appears

| Path | What it does |
| --- | --- |
| `design/landing-zone.yaml` | `shared_vpc`: host project, network name, region and the subnets with their service project and user groups. |
| `infra/modules/shared-vpc/` | Marks the host, attaches the service projects, creates the network, the subnets, the per-subnet grants and the deny-all rule. |
| `src/landing_zone/domain/design.py` | Checks that each subnet names a service project, has users and does not overlap another. |
| `src/landing_zone/domain/landscape.py` | `_vm` models the refusal when the caller's groups are not among the subnet's users. |
| `scripts/prove-network.sh` | Creates a VM per team and tries the wrong subnet. |
| `tests/unit/test_infrastructure_policy.py` | `networkUser` is granted on the subnet and nowhere else; no broad network role appears. |

## 4. How it works underneath

- A **custom-mode** network (`auto_create_subnetworks = false`) has no subnets until you create them; an **auto-mode** network creates one in every region, which is unwanted here.
- `compute.networkUser` granted on the **host project** would let the holder use every subnet, including subnets added later. Granted on one **subnet**, it covers that subnet only. The Google page on Shared VPC describes both and says subnet-level bindings should be reviewed when subnets are added.
- Creating machines in a shared subnet needs permission twice: in the **service project** (create instances) and on the **subnet** in the host project (`compute.subnetworks.use`). A caller who has only the first gets a refusal that names `compute.subnetworks.use`.
- Enabling a host project and attaching service projects is done by a **Shared VPC Admin** (`roles/compute.xpnAdmin`, granted on the organization or a folder), which the bootstrap script gives the operator.
- Every VPC has two **implied** firewall rules at the lowest priority: allow all egress, deny all ingress. Implied rules are not logged. An explicit deny rule at priority 65534 (just above the implied ones, since a lower number wins) behaves the same and can be logged.
- **Private Google Access** lets machines with no external address reach Google APIs. **VPC Flow Logs** record samples of the connections of a subnet.

## 5. Walkthrough of this repository's use

`design/landing-zone.yaml`

```yaml
shared_vpc:
  host_project: net-host
  network: shared-net
  region: europe-west1
  subnets:
    - name: subnet-prod
      cidr: 10.50.0.0/24
      service_project: prod-app
      user_groups:
        - group:team-prod@example-lab.org
    - name: subnet-dev
      cidr: 10.60.0.0/24
      service_project: dev-app
      user_groups:
        - group:team-dev@example-lab.org
```

`infra/modules/shared-vpc/main.tf`

```hcl
resource "google_compute_shared_vpc_host_project" "host" {
  project = var.host_project_id
}

resource "google_compute_shared_vpc_service_project" "service" {
  for_each = var.service_projects

  host_project    = google_compute_shared_vpc_host_project.host.project
  service_project = each.value
}
```

- The first resource turns `net-host` into a host. The second, with `for_each = var.service_projects`, attaches each service project to it.

`infra/modules/shared-vpc/main.tf`

```hcl
resource "google_compute_network" "this" {
  project                 = var.host_project_id
  name                    = var.network_name
  auto_create_subnetworks = false

  depends_on = [google_compute_shared_vpc_host_project.host]
}

resource "google_compute_subnetwork" "this" {
  for_each = var.subnets

  project                  = var.host_project_id
  name                     = each.key
  region                   = var.region
  network                  = google_compute_network.this.id
  ip_cidr_range            = each.value.cidr
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}
```

- `auto_create_subnetworks = false`: custom mode.
- `depends_on` makes the network wait until the project is a host.
- `private_ip_google_access = true`: machines without a public address can still reach Google APIs.
- `log_config` turns on flow logs: a record every 10 minutes (`INTERVAL_10_MIN`), half the connections sampled (`flow_sampling = 0.5`), with all metadata.

The key rule of the lesson, one grant per member, on the subnet:

`infra/modules/shared-vpc/main.tf`

```hcl
# Each team may use its own subnet and no other: networkUser is granted on the subnet, never on the host project.
resource "google_compute_subnetwork_iam_member" "network_user" {
  for_each = local.subnet_users

  project    = var.host_project_id
  region     = var.region
  subnetwork = google_compute_subnetwork.this[each.value.subnet].name
  role       = "roles/compute.networkUser"
  member     = each.value.member
}

locals {
  # Key: subnet plus position, so the keys are known at plan time even when a member is not.
  subnet_users = merge([
    for subnet, config in var.subnets : {
      for index, member in config.users : "${subnet}/${index}" => { subnet = subnet, member = member }
    }
  ]...)
```

`role = "roles/compute.networkUser"` on `google_compute_subnetwork_iam_member`: the resource type itself says "on a subnet". The `locals` flatten `{subnet = {users = [...]}}` into one entry per (subnet, member) with a key like `subnet-prod/0`.

The deny-all rule:

`infra/modules/shared-vpc/main.tf`

```hcl
resource "google_compute_firewall" "deny_all_ingress" {
  project   = var.host_project_id
  name      = "${var.network_name}-deny-all-ingress"
  network   = google_compute_network.this.id
  direction = "INGRESS"
  priority  = 65534

  source_ranges = ["0.0.0.0/0"]

  deny {
    protocol = "all"
  }

  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}
```

`priority = 65534` sits just above the implied rules; `source_ranges = ["0.0.0.0/0"]` matches everywhere; `deny { protocol = "all" }`; and `log_config` records each denial. Nothing is allowed in by this repository: the lesson's machines only need to be created, not reached.

The same rule in the simulator:

`src/landing_zone/domain/landscape.py`

```python
        if request.subnet is not None:
            subnet = self._design.subnet(request.subnet)
            if subnet is not None and not (set(subnet.user_groups) & request.caller_groups):
                return _refused(
                    Control.SHARED_VPC_IAM,
                    "compute.subnetworks.use",
                    f"Required 'compute.subnetworks.use' permission for 'projects/{self._design.host_project}/regions/"
                    f"{self._design.region}/subnetworks/{subnet.name}'",
                )
        return Decision()
```

`set(subnet.user_groups) & request.caller_groups` is the overlap of two sets: the groups allowed on the subnet and the groups the caller belongs to. An empty overlap is a refusal by `shared_vpc_iam` with the message the real service gives (`Required 'compute.subnetworks.use' permission ...`).

## 6. Try it yourself

```bash
.venv/bin/landing-zone simulate --mode enforced | grep -n "team-prod creates"
```
Expected: two lines. The first (on `subnet-prod`) says `allowed`; the second (on team-dev's subnet) says `REFUSED by shared_vpc_iam (compute.subnetworks.use)`.

```bash
.venv/bin/python -m pytest tests/unit/test_infrastructure_policy.py -q -p no:cacheprovider -k network_user
```
Expected: `1 passed`.

```bash
cd infra/modules/shared-vpc && terraform init -backend=false -input=false >/dev/null && terraform test
```
Expected: `Success! 5 passed, 0 failed.`

```bash
grep -rn "networkUser" infra --include=main.tf
```
Expected: two lines, both in `infra/modules/shared-vpc/main.tf`: a comment and the `role = "roles/compute.networkUser"` line.

```bash
.venv/bin/python -c "
import ipaddress as i
print(i.IPv4Network('10.50.0.0/24').overlaps(i.IPv4Network('10.60.0.0/24')))"
```
Expected: `False` (the two subnets do not share addresses).

## 7. Mistakes people make

- **Granting `networkUser` on the host project.** It covers every subnet, now and later. Grant it on the subnet.
- **Giving a team only the service-project role.** Creating a machine in the shared subnet fails with `compute.subnetworks.use`.
- **Overlapping ranges** between subnets, or with an on-premises network you may connect later.
- **Leaving the default network** in a service project, which sidesteps the shared one.
- **Expecting the implied deny to appear in logs.** It does not; the explicit rule is there to be logged.
- **Auto-mode networks.** They create a subnet in every region with fixed ranges.

## 8. Check yourself

1. What does the host project own? *The network, its subnets and its firewall rules.*
2. Why grant `networkUser` on a subnet and not on the host project? *To limit the holder to one subnet, now and when subnets are added.*
3. Which permission does a team lack when it uses the other team's subnet? *`compute.subnetworks.use`.*
4. Why is the firewall rule at priority 65534? *Just above the implied rules, so it behaves the same but can be logged.*
5. Can a project be both host and service project? *No.*

## 9. Further reading

- Shared VPC: <https://docs.cloud.google.com/vpc/docs/shared-vpc>
- VPC networks and subnets: <https://docs.cloud.google.com/vpc/docs/subnets>
- Firewall rules and implied rules: <https://docs.cloud.google.com/firewall/docs/firewalls>
- Terraform `google_compute_subnetwork_iam_member`: <https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_subnetwork_iam>
