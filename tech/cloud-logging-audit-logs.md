# Cloud Logging and audit logs

## 1. What it is

Cloud Logging stores logs from Google Cloud. **Cloud Audit Logs** are a family of those logs that record *who did what to which resource*. **Admin Activity** logs record changes to configuration and are always on. **Data Access** logs record reads and writes of data (for example an object read in Cloud Storage); for most services they are **off by default** and must be turned on, per service and per kind (`ADMIN_READ`, `DATA_READ`, `DATA_WRITE`). An audit entry keeps the caller, the method, the resource, the permission checked and the result. VPC Service Controls also writes its decisions into the audit log, as entries of a special type, for both real refusals and dry-run ones.

## 2. Why this repository uses it

Step 4 of the lesson depends on logs: with the perimeter in dry-run mode, you generate normal traffic, wait, and **read what the perimeter would have blocked** before you enforce. Step 5 reads the real violations and finds one by its identifier. Without audit logs the dry run teaches nothing.

## 3. Where it appears

| Path | What it does |
| --- | --- |
| `infra/modules/project/main.tf` | Turns on `ADMIN_READ`, `DATA_READ` and `DATA_WRITE` for `allServices` in every project. |
| `scripts/read-dry-run.sh` | Reads the dry-run violations (`dryRun=true`). |
| `scripts/attack.sh` | Reads the enforced violations (not dry run) after the attack. |
| `infra/modules/shared-vpc/main.tf` | Flow logs on the subnets and a logged deny-all firewall rule (network logs, a related but separate kind). |
| `docs/operating-notes.md` | Says which logs to read before enforcing. |

## 4. How it works underneath

An audit entry is a JSON document. The parts used here:

- `protoPayload.authenticationInfo.principalEmail`: who called.
- `protoPayload.metadata.@type`: the entry's type. `type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata` marks a VPC Service Controls decision.
- `protoPayload.metadata.dryRun`: `true` when the dry-run configuration produced the entry.
- `protoPayload.metadata.violationReason`: `NO_MATCHING_ACCESS_LEVEL` or `RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER` (see `vpc-service-controls.md`).
- `protoPayload.metadata.vpcServiceControlsUniqueId`: an identifier that ties one refusal to its log entries. The same value appears in the error the caller sees as `vpcServiceControlsUniqueIdentifier`.

`gcloud logging read 'FILTER'` returns entries that match a **filter** written in the Logging query language, such as `A AND NOT B`. `--freshness=1h` limits the search to the last hour and `--limit=5` keeps five. `--format='value(a, b)'` prints chosen fields only. Entries appear after a delay of a minute or more, which is why the scripts say "wait a few minutes".

## 5. Walkthrough of this repository's use

`infra/modules/project/main.tf`

```hcl
# Every API, admin and data access, is audited in every project: the proofs and the dry-run reviews read these logs.
resource "google_project_iam_audit_config" "all_services" {
  count = var.audit_all_services ? 1 : 0

  project = google_project.this.project_id
  service = "allServices"

  audit_log_config {
    log_type = "ADMIN_READ"
  }

  audit_log_config {
    log_type = "DATA_READ"
  }

  audit_log_config {
    log_type = "DATA_WRITE"
  }
}
```

`google_project_iam_audit_config` sets the audit configuration of one service in the project. `service = "allServices"` covers every service; the three `audit_log_config` blocks switch on admin reads, data reads and data writes. It is controlled by `count = var.audit_all_services ? 1 : 0`, which defaults to on.

Reading the dry-run violations:

`scripts/read-dry-run.sh`

```bash
echo "== dry-run violations: who was affected and why"
gcloud logging read 'protoPayload.metadata.dryRun=true AND protoPayload.metadata.@type="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata"' \
  --project="$PROD_DATA" --freshness=1h --limit=10 \
  --format='value(protoPayload.authenticationInfo.principalEmail, protoPayload.metadata.violationReason)'
echo "NO_MATCHING_ACCESS_LEVEL: add an access level for the caller (office_ip_subnetworks); RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER: add the project or an ingress rule."
```

- `protoPayload.metadata.dryRun=true AND protoPayload.metadata.@type=...` selects only dry-run perimeter entries.
- `--freshness=1h --limit=10` bounds the search; `--format='value(principalEmail, violationReason)'` prints one line per entry: who, and why.
- The last `echo` tells you what to do for each reason: add an access level for the caller, or add the project or an ingress rule.

Reading the enforced ones and finding one:

`scripts/attack.sh`

```bash
echo "== the violations in the audit log (IAM would have allowed both: the principal holds objectViewer)"
gcloud logging read 'protoPayload.metadata.@type="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata" AND NOT protoPayload.metadata.dryRun=true' \
  --project="$PROD_DATA" --freshness=1h --limit=5 \
  --format='value(protoPayload.authenticationInfo.principalEmail, protoPayload.metadata.violationReason, protoPayload.metadata.vpcServiceControlsUniqueId)'
echo "Find one by its identifier: gcloud logging read 'protoPayload.metadata.vpcServiceControlsUniqueId=\"ID\"' --project=$PROD_DATA"
```

`AND NOT protoPayload.metadata.dryRun=true` keeps real refusals. The final `echo` shows how to fetch one entry by `vpcServiceControlsUniqueId="ID"`.

## 6. Try it yourself

```bash
cd infra/modules/project && terraform init -backend=false -input=false >/dev/null && terraform test
```
Expected: `Success! 4 passed, 0 failed.` One of the four runs asserts `google_project_iam_audit_config.all_services[0].service == "allServices"`.

```bash
grep -n "log_type" infra/modules/project/main.tf
```
Expected: three lines: `ADMIN_READ`, `DATA_READ`, `DATA_WRITE`.

```bash
.venv/bin/landing-zone simulate --mode dry-run | grep "dry run would block" | cut -c1-120
```
Expected: two lines. This is what the dry-run log would hold for the two attacks.

```bash
grep -n "gcloud logging read" scripts/*.sh | cut -c1-90
```
Expected: three lines: one in `attack.sh`, one in `read-dry-run.sh`, and the hint in `attack.sh` for finding one entry by identifier.

With an organization (not run here): after `scripts/read-dry-run.sh`, wait a few minutes and run it again; the second run lists the violation entries.

## 7. Mistakes people make

- **Looking for Data Access logs that were never turned on.** For most services they are off by default.
- **Enforcing without reading the dry-run log.** The log is the whole reason for the dry run.
- **Searching without a time limit.** Add `--freshness`.
- **Expecting entries instantly.** There is a delay.
- **Turning on all data access logs in a busy project.** They can be large and cost money; this lab's projects are quiet.
- **Reading dry-run and enforced entries together.** Filter on `dryRun`.

## 8. Check yourself

1. Which audit logs are on by default? *Admin Activity.*
2. What does `metadata.dryRun=true` select? *Entries produced by the dry-run configuration.*
3. What does `vpcServiceControlsUniqueId` let you do? *Find the one log entry that matches a refusal the caller saw.*
4. What does `--freshness=1h` do? *Searches only the last hour.*
5. Why does the project module turn on data-access logs for all services? *The dry-run and attack reviews read them; without them there is nothing to read.*

## 9. Further reading

- Cloud Audit Logs: <https://docs.cloud.google.com/logging/docs/audit>
- Configure Data Access audit logs: <https://docs.cloud.google.com/logging/docs/audit/configure-data-access>
- Logging query language: <https://docs.cloud.google.com/logging/docs/view/logging-query-language>
- VPC Service Controls audit logging: <https://docs.cloud.google.com/vpc-service-controls/docs/audit-logging>
