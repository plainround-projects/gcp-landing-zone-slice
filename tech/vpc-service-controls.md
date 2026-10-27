# VPC Service Controls and Access Context Manager

## 1. What it is

**VPC Service Controls** draws a **perimeter** around Google Cloud projects and the Google services you choose to restrict (for example Cloud Storage and BigQuery). A request is allowed only if the caller and the resource are on the right side of that perimeter. It is a control **in addition to IAM**: IAM asks "does this identity have the permission?", the perimeter asks "is this request coming from where I trust, going where I trust?". Even a caller with full read permission is refused when the request crosses the perimeter badly.

**Access Context Manager** is the service that holds the perimeter's building blocks. An **access policy** is the container (one per organization in this setup). An **access level** is a named condition a caller can meet, such as "comes from these IP ranges". A perimeter can accept callers from outside if they match one of its access levels.

A perimeter has two configurations. The **enforced** one blocks. The **dry-run** one only logs what it would have blocked. By default the dry-run configuration copies the enforced one; Terraform lets you give a different, explicit dry-run configuration.

## 2. Why this repository uses it

Steps 4 and 5 of the lesson, and the lesson's main point: IAM alone does not stop **exfiltration**. The `data-reader` identity holds `roles/storage.objectViewer` on the bucket, so IAM allows it to read `customers.csv`. The attack copies the file to a bucket outside the organization, or reads it from a machine that matches no access level. IAM says yes both times; the perimeter says no.

## 3. Where it appears

| Path | What it does |
| --- | --- |
| `design/landing-zone.yaml` | `perimeter` (the protected projects, restricted services, accepted access levels) and `access_levels` (the `office` ranges). |
| `infra/modules/perimeter/` | Creates the access policy (or reuses one), the access level and the perimeter. |
| `src/landing_zone/domain/landscape.py` | `_copy`, `_read` and `_perimeter` model the two violations and the dry-run/enforced difference. |
| `src/landing_zone/domain/decision.py` | `PerimeterMode` and `Decision.logged_only` carry "logged, not blocked". |
| `scripts/read-dry-run.sh`, `scripts/attack.sh`, `scripts/enforce.sh` | Read the dry-run log, run the attack, flip to enforced. |
| `docs/operating-notes.md` | What the perimeter does not cover; the exception and break-glass process. |

## 4. How it works underneath

- The perimeter lists **projects** (by number) and **restricted services**. Calls to a restricted service about a project inside are checked; services not listed are not.
- A call from **outside** the perimeter into it is allowed only if an **access level** (or an ingress rule) matches the caller. A call that moves data **across** the boundary (copy from inside to a bucket outside) is refused with `RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER`. A caller who matches nothing gets `NO_MATCHING_ACCESS_LEVEL`. Google's troubleshooting page describes both reasons.
- A refusal returns HTTP 403 and an error that starts with "Request violates VPC Service Controls"; the audit log entry has status code 7 and a unique identifier (`vpcServiceControlsUniqueId`) so one denial can be found in the logs.
- **Dry run** writes the same entry with `metadata.dryRun` true and blocks nothing. Reading the dry-run log, fixing legitimate cases and only then enforcing is the safe order.
- The perimeter also stops **you**: once enforced, Terraform running on a laptop outside any access level cannot read the bucket either. The enforce script prints a warning and the teardown script relaxes the perimeter first.
- A perimeter does not protect against data an application shows on a web page, or against an insider who legitimately matches an access level. `docs/operating-notes.md` says so.
- This repository's scripts allow up to 30 minutes for a perimeter change to apply; the Google pages read for these notes do not give a figure.

## 5. Walkthrough of this repository's use

`design/landing-zone.yaml`

```yaml
perimeter:
  name: sensitive_data
  title: Sensitive data
  projects:
    - prod-data
  restricted_services:
    - storage.googleapis.com
    - bigquery.googleapis.com
  access_levels:
    - office

access_levels:
  - name: office
    # 203.0.113.0/24 is a documentation range. Put your own office or home address here (a /32 is enough).
    ip_subnetworks:
      - 203.0.113.0/24
```

The perimeter surrounds only `prod-data` and restricts Cloud Storage and BigQuery. The `office` access level is the documentation range `203.0.113.0/24`, which matches nobody: a laptop is outside it, which is what the second attack needs. Put your own address here to let yourself in.

`infra/modules/perimeter/main.tf`

```hcl
locals {
  access_policy_id = var.access_policy_id != "" ? var.access_policy_id : google_access_context_manager_access_policy.this[0].name
  parent           = "accessPolicies/${local.access_policy_id}"
  level_names      = [for name in var.access_level_names : "${local.parent}/accessLevels/${name}"]
  resources        = [for number in var.project_numbers : "projects/${number}"]
}
```

The names Google wants are paths: `accessPolicies/ID/accessLevels/NAME`, and `projects/NUMBER` for protected projects (the number, not the id).

`infra/modules/perimeter/main.tf`

```hcl
resource "google_access_context_manager_access_level" "this" {
  for_each = var.access_levels

  parent = local.parent
  name   = "${local.parent}/accessLevels/${each.key}"
  title  = each.key

  basic {
    conditions {
      ip_subnetworks = each.value
    }
  }
}
```

`basic { conditions { ip_subnetworks = ... } }` is the simplest access level: callers from these ranges.

`infra/modules/perimeter/main.tf`

```hcl
# `spec` is the dry-run configuration: violations are logged and nothing is blocked.
# `status` is the enforced configuration and is written only when mode = "enforced".
resource "google_access_context_manager_service_perimeter" "this" {
  parent         = local.parent
  name           = "${local.parent}/servicePerimeters/${var.name}"
  title          = var.title
  perimeter_type = "PERIMETER_TYPE_REGULAR"

  use_explicit_dry_run_spec = true

  spec {
    resources           = local.resources
    restricted_services = var.restricted_services
    access_levels       = local.level_names
  }

  dynamic "status" {
    for_each = var.mode == "enforced" ? [1] : []
    content {
      resources           = local.resources
      restricted_services = var.restricted_services
      access_levels       = local.level_names
    }
  }

  depends_on = [google_access_context_manager_access_level.this]
}
```

- `use_explicit_dry_run_spec = true` lets `spec` (dry run) differ from `status` (enforced). The provider's own description: the flag inhibits the generated implicit spec so you can test changes to the enforced config without enforcing them.
- `spec` is always written; `status` only when `mode = "enforced"`.
- `perimeter_type = "PERIMETER_TYPE_REGULAR"` is the ordinary kind: it holds resources, services and access levels (the other kind, a bridge, only connects perimeters).

The decision rules:

`src/landing_zone/domain/landscape.py`

```python
    def _copy(self, request: CopyObject) -> Decision:
        if not request.caller_can_read:
            return _refused(Control.IAM, "storage.objects.get", "the caller holds no role that allows the read")
        if self._in_perimeter(request.source_project) and not self._in_perimeter(request.destination_project):
            return self._perimeter(
                Violation(
                    Control.VPC_SERVICE_CONTROLS,
                    "RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER",
                    "Request is prohibited by organization's policy: the destination is outside the perimeter.",
                )
            )
        return Decision()
```

`src/landing_zone/domain/landscape.py`

```python
    def _in_perimeter(self, project: str) -> bool:
        perimeter = self._design.perimeter
        return project in perimeter.projects and _STORAGE in perimeter.restricted_services

    def _perimeter(self, violation: Violation) -> Decision:
        if self._mode is PerimeterMode.ENFORCED:
            return Decision(violations=(violation,))
        return Decision(logged_only=(violation,))
```

- A copy from a perimeter project to a project outside it is a `RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER` violation.
- A read of a perimeter project from an address that matches no trusted access level is `NO_MATCHING_ACCESS_LEVEL`.
- `_in_perimeter` is true only if the project is listed **and** Cloud Storage is restricted.
- `_perimeter` is where dry run and enforced differ: enforced returns `violations` (refused); dry run returns `logged_only` (allowed, but logged).

The attack and the evidence:

`scripts/attack.sh`

```bash
refused "copy to a bucket outside the perimeter" "vpcServiceControlsUniqueIdentifier" \
  gcloud storage cp "gs://$BUCKET/customers.csv" "gs://$OUTSIDE_BUCKET/" --impersonate-service-account="$DATA_READER_SA"
refused "read from a machine that matches no access level" "vpcServiceControlsUniqueIdentifier" \
  gcloud storage cat "gs://$BUCKET/customers.csv" --impersonate-service-account="$DATA_READER_SA"

echo "== the violations in the audit log (IAM would have allowed both: the principal holds objectViewer)"
gcloud logging read 'protoPayload.metadata.@type="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata" AND NOT protoPayload.metadata.dryRun=true' \
  --project="$PROD_DATA" --freshness=1h --limit=5 \
  --format='value(protoPayload.authenticationInfo.principalEmail, protoPayload.metadata.violationReason, protoPayload.metadata.vpcServiceControlsUniqueId)'
echo "Find one by its identifier: gcloud logging read 'protoPayload.metadata.vpcServiceControlsUniqueId=\"ID\"' --project=$PROD_DATA"
exit "$FAILED"
```

Both attacks run as `data-reader`; the expected text is `vpcServiceControlsUniqueIdentifier`, which appears in the refusal. The log query then lists the violations, filtered with `NOT protoPayload.metadata.dryRun=true`, so only enforced refusals show.

## 6. Try it yourself

```bash
.venv/bin/landing-zone simulate --mode dry-run | grep -E "outside|laptop"
```
Expected: two lines, each beginning `ok` and saying `allowed, but dry run would block:` with `RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER` and `NO_MATCHING_ACCESS_LEVEL`.

```bash
.venv/bin/landing-zone simulate --mode enforced | grep -E "outside|laptop"
```
Expected: the same two requests, now `REFUSED by vpc_service_controls (...)`.

```bash
.venv/bin/python -m pytest tests/e2e -q -p no:cacheprovider
```
Expected: `3 passed`, including the test that the attack is refused when enforced and only logged in dry run.

```bash
cd infra/modules/perimeter && terraform init -backend=false -input=false >/dev/null && terraform test
```
Expected: `Success! 6 passed, 0 failed.`

```bash
.venv/bin/python -m pytest tests/unit/test_infrastructure_policy.py -q -p no:cacheprovider -k "perimeter"
```
Expected: `2 passed`: the perimeter defaults to dry run, and it keeps a separate dry-run configuration.

## 7. Mistakes people make

- **Thinking IAM is enough.** A principal with the right role can still copy data out; the perimeter is the second lock.
- **Enforcing without a dry run.** Normal traffic from an unlisted address is suddenly refused.
- **Locking yourself out.** An enforced perimeter blocks your own laptop and your Terraform. Add your address to an access level first, or relax the perimeter before teardown.
- **Forgetting the access level.** The office range is a documentation range by default.
- **Using the project id instead of the number** in the perimeter's resources.
- **Believing the perimeter covers everything.** Services not listed, application pages and insiders with a legitimate access level are outside it.

## 8. Check yourself

1. What does the perimeter add to IAM? *A check on where the request comes from and where the data goes.*
2. What does a dry-run perimeter do with a violation? *Logs it and allows the request.*
3. What is an access level? *A named condition a caller can meet, such as an IP range.*
4. Which reason is logged when a copy leaves the perimeter? *`RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER`.*
5. Why can an enforced perimeter break Terraform on your laptop? *Your address matches no access level, so you are an outsider too.*

## 9. Further reading

- VPC Service Controls overview: <https://docs.cloud.google.com/vpc-service-controls/docs/overview>
- Dry run mode: <https://docs.cloud.google.com/vpc-service-controls/docs/dry-run-mode>
- Troubleshooting and violation reasons: <https://docs.cloud.google.com/vpc-service-controls/docs/troubleshooting>
- Access Context Manager: <https://docs.cloud.google.com/access-context-manager/docs/overview>
