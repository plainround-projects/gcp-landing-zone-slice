# Operating notes for the landing-zone slice

Step 6 of the lesson. These notes are written for the platform team that owns this repository and for a team that wants something the guardrails refuse.

## How a team requests an exception

1. **Who asks.** The team lead opens a pull request that changes the smallest thing that gives the exception: usually one entry in `policies/org-policies.yaml` with `level: folder:NAME` (a folder-level policy replaces the organization's for that folder), or one more address range in the `office` access level, or one more project in a perimeter's ingress rule. The pull request says what the team is trying to do, which request was refused, and what they tried instead (every policy file entry already lists "instead").
2. **Who approves.** One member of the platform team and one member of the security team, by code owner rules on `policies/` and `design/`. The platform team may refuse and suggest the alternative; the security team may refuse a loosening of the data perimeter on its own.
3. **How long it lasts.** An exception has an end date in the pull request description and in a comment above the entry; a reviewer checks the file for expired exceptions every month. The default is 90 days.
4. **Where it is recorded.** In this repository. The perimeter and the policies are code, so the change is the pull request, its approvals and the Terraform apply that follows. Nothing is changed in the console.

## How a change is tested (the dry run is mandatory)

No change to a policy or to the perimeter goes straight to enforcement. A perimeter blocks calls that IAM allows, so it can break working systems, and a policy can refuse a creation that a pipeline depends on.

1. Run `make design simulate`: the design is consistent, and every request in `design/scenarios.yaml` is answered as promised, with the perimeter in dry-run and enforced mode. Add a scenario for the new case first.
2. Apply with `policy_mode = "dry_run"` and `perimeter_mode = "dry_run"` (the defaults). Policies get only their dry-run spec; the perimeter gets only its dry-run configuration. Violations are logged; nothing is blocked.
3. Watch the logs (`scripts/read-dry-run.sh`) for **at least one full business cycle**, a week at minimum, long enough for the monthly job and the weekly report to run. Every `NO_MATCHING_ACCESS_LEVEL` and `RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER` line is either a legitimate call (add an access level, an ingress rule or the project) or a call that should stop.
4. Enforce with `scripts/enforce.sh` (it asks you to confirm that step 3 is done). Allow up to 30 minutes for the change to apply before you test, and test with a principal that **can** read the data: a principal without read permission is stopped by IAM and tells you nothing about the perimeter.
5. Keep the dry-run configuration. It stays in the perimeter as the staging area for the next change.

## What the perimeter does not protect against

- **Data shown by an application.** If a service inside the perimeter returns customer rows in an HTTP response to a user, the perimeter has done its job and the data still leaves. Application authorization and output review cover this.
- **Services that are not restricted.** The perimeter restricts `storage.googleapis.com` and `bigquery.googleapis.com`. Data in Pub/Sub, a Cloud SQL instance or a persistent disk is outside it until the service is added.
- **An insider with a legitimate access level.** Someone on the office network with `objectViewer` can read and copy the data to a machine inside the same network. Detective controls (data access audit logs, alerts on unusual volume) cover this.
- **Projects added to the perimeter by mistake.** The perimeter protects what is listed. A new data project is unprotected until the design file lists it.
- **Metadata and some administrative calls.** Some APIs and methods are not subject to the perimeter; the product documentation lists the supported services and the limits. Read it before relying on the perimeter for a service.
- **Terraform itself.** After enforcement, a laptop outside the access level cannot read the bucket, and so cannot refresh Terraform's view of it. That is the control working, and a reason to run Terraform from a pipeline inside an access level.

## Break glass: who can change the perimeter, and how you notice

- **Who.** Only the platform team's `accesscontextmanager.policyAdmin` group (two people at most), and only through Terraform from the pipeline. Nobody has the role standing in their own account; it is granted for the change window and removed after.
- **How it is logged.** Every change to the access policy, an access level or the perimeter is an Admin Activity audit log entry of `accesscontextmanager.googleapis.com`. A log-based alert sends any `UpdateServicePerimeter`, `DeleteServicePerimeter` or `ReplaceServicePerimeters` call to the security channel, and the pull request must exist for the same change.
- **How you notice a silent loosening.** `terraform plan` runs on a schedule; a difference between the code and the live perimeter opens an incident. The dry-run configuration should always equal or tighten the enforced one.
- **Emergency access to the data.** A named, time-limited access level (for example the incident room's address) is added by pull request with the same approvals, using the expedited review path, and removed within the day.
