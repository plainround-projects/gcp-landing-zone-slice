# Organization policy

## 1. What it is

An **organization policy** is a rule set on the organization, a folder or a project that limits what anyone in that part of the tree may do, **whatever their IAM permissions are**. IAM answers "may this person do it?"; an organization policy answers "may it be done here at all?". Each rule is a **constraint** with a name such as `iam.disableServiceAccountKeyCreation`. A **boolean** constraint is enforced or not. A **list** constraint allows a set of values, or denies all. A policy set high is inherited by everything below, and a lower level can override it. A policy can also be written in **dry-run** form: it is evaluated like a normal policy, but violations are only written to the audit log and nothing is blocked.

## 2. Why this repository uses it

Step 2 of the lesson: stop four risky requests before they happen, whoever asks. Each policy has a reason and a named request it blocks:

| Constraint | Blocks |
| --- | --- |
| `iam.disableServiceAccountKeyCreation` | downloading a service account key |
| `gcp.resourceLocations` (`in:eu-locations`) | a bucket outside the EU |
| `storage.uniformBucketLevelAccess` | per-object ACLs on a bucket |
| `compute.vmExternalIpAccess` (deny all) | a VM with a public address |

## 3. Where it appears

| Path | What it does |
| --- | --- |
| `policies/org-policies.yaml` | The four policies as data, with reason, blocked request and the alternative. |
| `src/landing_zone/domain/policy.py` | `OrgPolicy` rejects an entry with no reason or a contradictory kind. |
| `src/landing_zone/application/render.py` | Writes the documents `gcloud org-policies set-policy` takes; `explain` prints the table. |
| `src/landing_zone/domain/landscape.py` | Models what each policy refuses, to answer "who stops this request?". |
| `infra/modules/org-policies/` | Writes the policies with Terraform: dry-run spec always, enforced spec only on request. |
| `scripts/render-policies.sh`, `enforce.sh`, `prove-policies.sh` | The no-Terraform route, the switch to enforced, and the proof. |

## 4. How it works underneath

- A **policy** for one constraint at one place holds a list of **rules**. A boolean rule says `enforce: true`. A list rule says `allowedValues`, `deniedValues`, `allowAll` or `denyAll`. Written for the command line, the policy is a YAML document with `name` (the parent, `/policies/`, the constraint) and `spec` or `dryRunSpec`.
- **Value groups** keep lists short. `in:eu-locations` means "every location in the EU" and Google maintains the group. The prefix `in:` is part of the value.
- Policies are checked **when a resource is created or changed**; they are not retroactive. A bucket that already exists in the US keeps running, and a policy does not find it (a different tool does).
- Because a violating request is refused with a message naming the constraint (for example `Constraint constraints/gcp.resourceLocations violated`), the message is the evidence of which control spoke.
- **Dry run first.** The `dryRunSpec` logs what the policy would have refused. You read the log, fix the legitimate cases, then enforce. Skipping this step breaks a team's pipeline on a Friday.
- This repository's scripts allow up to 30 minutes for a change to apply before testing, as a safe assumption; the Google pages read for these notes give no figure.

## 5. Walkthrough of this repository's use

`policies/org-policies.yaml`

```yaml
policies:
  - constraint: iam.disableServiceAccountKeyCreation
    kind: boolean
    enforce: true
    level: organization
    reason: A downloaded key is a password that never expires and cannot be tied to a person; workloads use the platform's short-lived credentials.
    blocks:
      request: A developer wants to download a key for a service account to run a script from a laptop.
      instead: Impersonate the service account with their own identity, or use workload identity federation.
```

`kind: boolean` with `enforce: true` is the first policy. The second is `kind: list` with `allowed_values`; the fourth uses `deny_all: true`. `level: organization` sets it at the top; `level: folder:production` would set it on a folder. Each has a `reason` and `blocks.request` and `blocks.instead`: the lesson asks for both.

The Python type refuses an incomplete entry:

`src/landing_zone/domain/policy.py`

```python
    def __post_init__(self) -> None:
        """Reject entries that are incomplete for their kind or cannot be defended."""
        if not self.constraint or "/" in self.constraint:
            raise InvalidPolicy(f"not a constraint name: {self.constraint!r}")
        if not self.reason.strip():
            raise InvalidPolicy(f"{self.constraint}: a policy with no reason is a rule you cannot defend")
        if not self.blocked_request.strip() or not self.instead.strip():
            raise InvalidPolicy(f"{self.constraint}: name one team request it blocks and what to do instead")
        if self.level != "organization" and not self.level.startswith("folder:"):
            raise InvalidPolicy(f"{self.constraint}: level must be 'organization' or 'folder:NAME', got {self.level!r}")
        if self.kind is PolicyKind.BOOLEAN and (self.allowed_values or self.deny_all):
            raise InvalidPolicy(f"{self.constraint}: a boolean constraint takes only enforce")
        if self.kind is PolicyKind.LIST:
            if self.enforce:
                raise InvalidPolicy(
                    f"{self.constraint}: a list constraint takes allowed_values or deny_all, not enforce"
                )
            if bool(self.allowed_values) == self.deny_all:
                raise InvalidPolicy(f"{self.constraint}: give exactly one of allowed_values and deny_all")
```

The rendering to the `gcloud` document:

`src/landing_zone/application/render.py`

```python
def render_policy_document(
    policy: OrgPolicy, organization_id: str, *, dry_run: bool, folder_ids: dict[str, str] | None = None
) -> dict[str, Any]:
    """One policy as the dict behind the gcloud YAML; `dry_run` writes `dryRunSpec` so the policy only logs."""
    parent = f"organizations/{organization_id}"
    if policy.folder is not None:
        folder_id = (folder_ids or {}).get(policy.folder)
        if folder_id is None:
            raise KeyError(f"no folder id for {policy.folder}: pass it with --folder NAME=ID")
        parent = f"folders/{folder_id}"
    if policy.kind is PolicyKind.BOOLEAN:
        rule: dict[str, Any] = {"enforce": policy.enforce}
    elif policy.deny_all:
        rule = {"denyAll": True}
    else:
        rule = {"values": {"allowedValues": list(policy.allowed_values)}}
    return {"name": f"{parent}/policies/{policy.constraint}", "dryRunSpec" if dry_run else "spec": {"rules": [rule]}}
```

- `parent` is `organizations/ID`, or `folders/ID` for a folder policy (it needs the id: `--folder NAME=ID`).
- A boolean policy becomes `{"enforce": ...}`; deny-all becomes `{"denyAll": True}`; an allow list becomes `{"values": {"allowedValues": [...]}}`.
- The key is `dryRunSpec` when `dry_run` is true and `spec` otherwise. That one word is the difference between logging and blocking.

What a request meets, modelled in the simulator:

`src/landing_zone/domain/landscape.py`

```python
    def _bucket(self, request: CreateBucket) -> Decision:
        project = self._design.project(request.project)
        locations = self._policy("gcp.resourceLocations", project)
        if locations is not None and not _location_allowed(request.location, locations.allowed_values):
            return _refused(
                Control.ORG_POLICY,
                locations.constraint,
                f"Constraint constraints/gcp.resourceLocations violated for [projects/{request.project}] "
                f"attempting to create a bucket in {request.location}.",
            )
        uniform = self._policy("storage.uniformBucketLevelAccess", project)
        if uniform is not None and uniform.enforce and not request.uniform_access:
            return _refused(
                Control.ORG_POLICY,
                uniform.constraint,
                f"Constraint constraints/storage.uniformBucketLevelAccess violated for [projects/{request.project}].",
            )
        return Decision()
```

The location rule is a simplification: the simulator treats `EU` and any name starting with `europe-` as inside `in:eu-locations`, which is true for `europe-west1` but is not how Google defines the group (some `europe-` regions, such as London, are not in the EU). The tests and the lesson only use EU regions.

The Terraform side:

`infra/modules/org-policies/main.tf`

```hcl
resource "google_org_policy_policy" "this" {
  for_each = local.policies

  name   = "${local.parents[each.key]}/policies/${each.value.constraint}"
  parent = local.parents[each.key]

  dry_run_spec {
    rules {
      enforce  = local.rules[each.key].enforce
      deny_all = local.rules[each.key].deny_all

      dynamic "values" {
        for_each = length(local.rules[each.key].allowed_values) > 0 ? [1] : []
        content {
          allowed_values = local.rules[each.key].allowed_values
        }
      }
    }
  }

  dynamic "spec" {
    for_each = var.mode == "enforced" ? [1] : []
    content {
      rules {
        enforce  = local.rules[each.key].enforce
        deny_all = local.rules[each.key].deny_all

        dynamic "values" {
          for_each = length(local.rules[each.key].allowed_values) > 0 ? [1] : []
          content {
            allowed_values = local.rules[each.key].allowed_values
          }
        }
      }
    }
  }
}
```

The provider describes `dry_run_spec` as an audit-only policy that monitors how the policy would have impacted existing and future resources if enforced. See `terraform.md` for the `dynamic` block.

The proof, with the policies enforced:

`scripts/prove-policies.sh`

```bash
refused "creating a service account key" "Key creation is not allowed" \
  gcloud iam service-accounts keys create /dev/null --iam-account="$TEAM_DEV_SA" --project="$DEV_APP"
refused "a bucket in us-central1" "constraints/gcp.resourceLocations" \
  gcloud storage buckets create "gs://$DEV_APP-us-test" --project="$DEV_APP" --location=us-central1
refused "a VM with a public IP address in dev-app" "constraints/compute.vmExternalIpAccess" \
  gcloud compute instances create vm1 --project="$DEV_APP" --zone="$REGION-b" \
    --subnet="projects/$NET_HOST/regions/$REGION/subnetworks/subnet-dev" --machine-type=e2-micro \
    --no-service-account --no-scopes --impersonate-service-account="$TEAM_DEV_SA"
refused "a bucket with per-object ACLs" "constraints/storage.uniformBucketLevelAccess" \
  gcloud storage buckets create "gs://$DEV_APP-acl-test" --project="$DEV_APP" --location="$REGION" --no-uniform-bucket-level-access

exit "$FAILED"
```

Each `refused` line demands both a failure and the constraint's name in the message.

## 6. Try it yourself

```bash
.venv/bin/landing-zone explain | head -3 | cut -c1-90
```
Expected: the Markdown table header `| Constraint | Level | Reason | A request it blocks | Instead |`, the `| --- |` line, then the first policy row.

```bash
OUT=$(mktemp -d); .venv/bin/landing-zone render-policies --org 123456789012 --dry-run --out "$OUT" >/dev/null; cat "$OUT/gcp.resourceLocations.yaml"; rm -r "$OUT"
```
Expected:
```text
name: organizations/123456789012/policies/gcp.resourceLocations
dryRunSpec:
  rules:
  - values:
      allowedValues:
      - in:eu-locations
```

```bash
.venv/bin/landing-zone simulate --mode enforced | sed -n 1,4p
```
Expected: four lines starting with `ok`: the key is refused by `org_policy (iam.disableServiceAccountKeyCreation)`, the `us-central1` bucket by `gcp.resourceLocations`, the `europe-west1` bucket is `allowed`, and the bucket with per-object ACLs is refused by `storage.uniformBucketLevelAccess`.

```bash
.venv/bin/python -m pytest tests/unit/domain/test_policy.py -q -p no:cacheprovider
```
Expected: all pass (the rejected-entry cases run once per message).

```bash
cd infra/modules/org-policies && terraform init -backend=false -input=false >/dev/null && terraform test
```
Expected: `Success! 6 passed, 0 failed.`

## 7. Mistakes people make

- **Enforcing without a dry run.** Legitimate work breaks with no warning.
- **Testing too soon.** A change takes time to apply; a test that "still works" proves nothing yet.
- **Thinking a policy removes existing violations.** It guards creation; it does not clean up.
- **A policy with no reason.** The type refuses it: a rule you cannot defend gets removed in the first complaint.
- **Setting everything on the organization.** Put an exception on the narrowest folder, and record it.
- **Trusting the simulator's location rule as Google's definition.** It is a teaching simplification.

## 8. Check yourself

1. How is an organization policy different from IAM? *IAM grants a person permission; the policy limits what is allowed in that part of the tree regardless of permission.*
2. What does `dryRunSpec` do? *The policy is evaluated and violations are logged, but nothing is blocked.*
3. What does `in:eu-locations` mean? *A Google-maintained group: every EU location.*
4. Does a new policy remove a bucket that already breaks it? *No; policies guard creation and changes.*
5. Why does each policy entry carry `blocks.instead`? *A refusal without an alternative sends people around the rule.*

## 9. Further reading

- Organization Policy overview: <https://docs.cloud.google.com/resource-manager/docs/organization-policy/overview>
- Restricting resource locations: <https://docs.cloud.google.com/resource-manager/docs/organization-policy/defining-locations>
- Constraints list: <https://docs.cloud.google.com/resource-manager/docs/organization-policy/org-policy-constraints>
- `gcloud org-policies`: <https://docs.cloud.google.com/sdk/gcloud/reference/org-policies>
