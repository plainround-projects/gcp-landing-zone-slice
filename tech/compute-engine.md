# Compute Engine (the test virtual machines)

## 1. What it is

Compute Engine rents virtual machines (VMs) by the second. A VM has a **machine type** (how many CPUs and how much memory; `e2-micro` is among the smallest), a **zone** (a data-center area inside a region, such as `europe-west1-b`), a **network interface** in a subnet, and optionally an **external IP address** that makes it reachable from the internet. It can also run as a **service account** with **scopes** (a legacy limit on which APIs the VM's token may call).

## 2. Why this repository uses it

The lesson never needs a VM to *do* anything. VMs are the cheapest way to **prove** two controls from outside the Python model:

- Step 2: a VM with a public address must be refused by the organization policy `compute.vmExternalIpAccess`.
- Step 3: each team creates a VM in its own subnet and gets an address from the right range, and cannot create one in the other team's subnet.

Every VM is deleted at the end of the proof.

## 3. Where it appears

| Path | What it does |
| --- | --- |
| `scripts/prove-policies.sh` | Tries to create a VM with a public address; expects the constraint's name in the refusal. |
| `scripts/prove-network.sh` | Creates `vm1` and `vm2` with no external address; tries `vm3` and `vm4` in the wrong subnet; deletes `vm1` and `vm2`. |
| `infra/modules/lab-identities/main.tf` | Gives each team's stand-in `roles/compute.instanceAdmin.v1` in its own project. |
| `infra/environments/lab/main.tf` | Enables the `compute.googleapis.com` API in the service and host projects. |
| `src/landing_zone/domain/requests.py`, `landscape.py` | `CreateVm` and `_vm` model the two refusals. |
| `design/scenarios.yaml` | Four VM scenarios. |

## 4. How it works underneath

- A VM is created with **two** checks that are easy to mix up: a permission in the project that will own the VM (`compute.instances.create`, from `roles/compute.instanceAdmin.v1`), and a permission on the **subnet** it will use (`compute.subnetworks.use`, from `roles/compute.networkUser` on the subnet, see `shared-vpc-and-networking.md`). Missing the second gives an error that names `compute.subnetworks.use`.
- `--subnet=projects/HOST/regions/REGION/subnetworks/NAME` names a subnet of the shared network by its full path, because the subnet lives in the host project, not in the project that owns the VM.
- By default `gcloud compute instances create` also gives the VM an external address (an *ephemeral* one: it changes when the VM stops). `--no-address` says "no external address". A list constraint `compute.vmExternalIpAccess` with `denyAll` refuses any VM that asks for one.
- `--no-service-account --no-scopes` creates the VM with no identity of its own, so a throwaway VM cannot call any API.
- The VM's internal address comes from its subnet's range, so `10.50.0.*` proves it was placed in `subnet-prod`.
- Machines cost money while they exist. The scripts delete them (`gcloud compute instances delete ... --quiet`).

## 5. Walkthrough of this repository's use

`scripts/prove-policies.sh`

```bash
refused "a VM with a public IP address in dev-app" "constraints/compute.vmExternalIpAccess" \
  gcloud compute instances create vm1 --project="$DEV_APP" --zone="$REGION-b" \
    --subnet="projects/$NET_HOST/regions/$REGION/subnetworks/subnet-dev" --machine-type=e2-micro \
    --no-service-account --no-scopes --impersonate-service-account="$TEAM_DEV_SA"
```

- There is no `--no-address`, so the VM asks for a public address and must be refused with `constraints/compute.vmExternalIpAccess`.
- The line runs as the team-dev stand-in (`--impersonate-service-account`), which holds the right to create VMs. The refusal therefore comes from the policy, not from a missing permission.

`scripts/prove-network.sh`

```bash
vm() { # vm NAME PROJECT SUBNET IDENTITY
  gcloud compute instances create "$1" --project="$2" --zone="$REGION-b" --machine-type=e2-micro \
    --subnet="projects/$NET_HOST/regions/$REGION/subnetworks/$3" --no-address --no-service-account --no-scopes \
    --impersonate-service-account="$4"
}
address() { gcloud compute instances list --project="$1" --filter="name=$2" --format='value(networkInterfaces[0].networkIP)'; }

vm vm1 "$PROD_APP" subnet-prod "$TEAM_PROD_SA" >/dev/null
vm vm2 "$DEV_APP" subnet-dev "$TEAM_DEV_SA" >/dev/null
```

- `--machine-type=e2-micro` is the cheapest choice. `--zone="$REGION-b"` builds `europe-west1-b`.
- `--no-address` keeps the machine private; `--no-service-account --no-scopes` gives it no identity.

`scripts/prove-network.sh`

```bash
check "the VM in prod-app has an address in 10.50.0.0/24" bash -c "[[ \"\$(gcloud compute instances list --project='$PROD_APP' --filter='name=vm1' --format='value(networkInterfaces[0].networkIP)')\" == 10.50.0.* ]]"
check "the VM in dev-app has an address in 10.60.0.0/24" bash -c "[[ \"\$(gcloud compute instances list --project='$DEV_APP' --filter='name=vm2' --format='value(networkInterfaces[0].networkIP)')\" == 10.60.0.* ]]"
echo "prod-app vm1: $(address "$PROD_APP" vm1)   dev-app vm2: $(address "$DEV_APP" vm2)"

refused "team-prod in team-dev's subnet" "compute.subnetworks.use" vm vm3 "$PROD_APP" subnet-dev "$TEAM_PROD_SA"
refused "team-dev in team-prod's subnet" "compute.subnetworks.use" vm vm4 "$DEV_APP" subnet-prod "$TEAM_DEV_SA"
```

- `gcloud compute instances list --filter='name=vm1' --format='value(networkInterfaces[0].networkIP)'` prints only the VM's internal address; the test checks it starts with `10.50.0.`.
- The two `refused` lines are the point: team-prod's stand-in asks for `subnet-dev` and gets a refusal containing `compute.subnetworks.use`.

How the model reads a VM request:

`src/landing_zone/domain/requests.py`

```python
class CreateVm:
    """Create a VM in `project`; `subnet` is a subnet of the shared VPC, `caller_groups` the groups of the caller."""

    project: str
    zone: str
    subnet: str | None
    external_ip: bool
    caller_groups: frozenset[str]
```

`src/landing_zone/domain/landscape.py`

```python
    def _vm(self, request: CreateVm) -> Decision:
        project = self._design.project(request.project)
        external = self._policy("compute.vmExternalIpAccess", project)
        if request.external_ip and external is not None and external.deny_all:
            return _refused(
                Control.ORG_POLICY,
                external.constraint,
                f"Constraint constraints/compute.vmExternalIpAccess violated for project {request.project}.",
            )
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

The public-address check comes first (an organization policy), the subnet check second (Shared VPC IAM). A request with no shared subnet is subject only to the policies.

## 6. Try it yourself

```bash
.venv/bin/landing-zone simulate --mode enforced | grep VM
```
Expected: four lines. The public-address VM is `REFUSED by org_policy (compute.vmExternalIpAccess)`; the private VM in `subnet-dev` and team-prod's VM in `subnet-prod` are `allowed`; team-prod's VM on team-dev's subnet is `REFUSED by shared_vpc_iam (compute.subnetworks.use)`.

```bash
.venv/bin/python -m pytest tests/unit/domain/test_landscape.py -q -p no:cacheprovider -k "vm"
```
Expected: all selected tests pass (the VM cases, including the one with no shared subnet).

```bash
gcloud compute instances create --help | grep -A3 -E "^ +--no-address"
```
Expected: the help text of `--no-address`: the instances are not assigned external IP addresses. (Needs the Google Cloud SDK, not an account.)

```bash
grep -c "e2-micro" scripts/*.sh | grep -v ":0"
```
Expected: `scripts/prove-network.sh:1` and `scripts/prove-policies.sh:1`.

With an organization (not run here): `make prove` runs the real versions and ends with `PASS` lines; the VMs exist for a few minutes.

## 7. Mistakes people make

- **Forgetting the VM is billed while it exists.** Delete it.
- **Granting `compute.instanceAdmin` and expecting the subnet to work.** The subnet needs its own grant.
- **Passing only the subnet name** when the subnet is in another project. Use the full path.
- **Reading "no external IP" as "no internet".** The VM may still reach Google APIs through Private Google Access; reaching the wider internet needs Cloud NAT.
- **Giving a throwaway VM a service account.** `--no-service-account` leaves it with no identity.

## 8. Check yourself

1. Which two permissions does a VM in a shared subnet need? *One in its own project to create instances; one on the subnet (`compute.subnetworks.use`).*
2. What does `--no-address` do? *The VM gets no external IP address.*
3. Why does the proof use `e2-micro`? *It is cheap, and the VM only has to exist for a moment.*
4. How does the proof show a VM is in `subnet-prod`? *Its internal address starts with `10.50.0.`.*
5. Why delete the VMs at the end? *They are billed while they exist.*

## 9. Further reading

- Compute Engine instances: <https://docs.cloud.google.com/compute/docs/instances>
- `gcloud compute instances create`: <https://docs.cloud.google.com/sdk/gcloud/reference/compute/instances/create>
- Machine families (E2): <https://docs.cloud.google.com/compute/docs/general-purpose-machines#e2_machine_types>
- Private Google Access: <https://docs.cloud.google.com/vpc/docs/private-google-access>
