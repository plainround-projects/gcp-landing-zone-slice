# gcp-landing-zone-slice

A slice of a Google Cloud landing zone as code: folders, four organization policies, a shared VPC where each team uses only its own subnet, and a VPC Service Controls perimeter around the sensitive data, all in Terraform with dry-run mode first, plus a tool that checks the design and simulates which control stops a request.

| | |
| --- | --- |
| **Lesson** | `/prep/gcp/project-landing-zone-slice`, "Build a landing-zone slice with a perimeter" (`data-structure-explainer/src/content/tracks/gcp/17-project-landing-zone-slice.md` in the Plainround app) |
| **Planned hours** | 14 |
| **Level** | Advanced |
| **Architecture** | [ARCHITECTURE.md](ARCHITECTURE.md), decisions in [docs/adr](docs/adr), operating notes in [docs/operating-notes.md](docs/operating-notes.md) |
| **Author** | Sumit Srivastava |

## What is here

- `design/landing-zone.yaml` and `policies/org-policies.yaml`: the slice and the four policies as data, each policy with its reason and the team request it blocks. Terraform and the tool both read them.
- `infra/`: Terraform (`google` provider `~> 8.8`), seven modules and one environment, `lab`: folders, projects, organization policies (dry run first), the shared VPC, the sensitive bucket, the perimeter (dry run first) and keyless test identities.
- `src/landing_zone/`: the `landing-zone` command: `check` the design, `explain` the policies, `render-policies` into the YAML `gcloud org-policies set-policy` takes, `simulate` the lesson's requests in dry-run and enforced mode.
- `scripts/`: the lesson's runbook as the exact `gcloud` and `terraform` commands: bootstrap, deploy, prove each Done when line, read the dry run, enforce, attack, tear down.
- `docs/operating-notes.md`: step 6, the exception process, how a change is tested, what the perimeter does not cover, break glass.
- `tech/`: 33 notes, one per technology (Python, Terraform, Bash, Make, each Google Cloud service and every tool), written for a reader who has never met them. Start with [tech/README.md](tech/README.md).

**No organization exists yet, so nothing has run against one.** Everything that can be checked without it is: the design and policies are validated, the lesson's 13 requests are answered as promised by the simulator, the Terraform is validated, planned offline (50 resources) and tested against a mock provider. The refusals, the dry-run log lines and the violation identifiers need the organization; the commands for them are ready (see "Done when").

## Prerequisites

| Tool | Version | Used for |
| --- | --- | --- |
| Python | 3.12 or 3.13 (tested with 3.13; CI uses 3.12) | the `landing-zone` tool and tests |
| GNU Make | 3.81 or newer | every command below |
| Terraform | 1.9 or newer (tested with 1.17.0) | `make lint`, `make test`, `make validate`, deploy |
| tflint | 0.65 or newer (Google ruleset 0.41.0 via `tflint --init`) | `make lint` |
| checkov | 3.x (`uv tool install checkov` or `pip install checkov`) | `make validate` |
| shellcheck | 0.9 or newer | `make lint` |
| Google Cloud CLI (`gcloud`) | current | only the deploy steps |
| **An organization you own** | a free Cloud Identity domain gives you one | only the deploy steps |
| A billing account | a free-trial or paid one | only the deploy steps |

No Docker. The deploy steps need an organization administrator once (`scripts/bootstrap.sh` grants the operator the roles it needs), a billing account, a bucket in a project outside the organization for the copy attack, and two groups (`team-prod`, `team-dev`) or the lab's test identities, which the build creates.

## Run it on this machine (no cloud account)

```bash
make install        # .venv from the hash-pinned lock file
make design         # check the design and policies; print each policy with its reason and the request it blocks
make simulate       # the lesson's 13 requests, answered with the perimeter in dry run and then enforced
make run            # both of the above
```

`make simulate` prints one line per request. The attack of step 5, from the enforced run and the dry run:

```text
ok    a reader copies customers.csv to a bucket outside the organization: REFUSED by vpc_service_controls (RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER)
ok    a reader copies customers.csv to a bucket outside the organization: allowed, but dry run would block: RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER
```

The policy files for the `gcloud` route (no Terraform):

```bash
.venv/bin/landing-zone render-policies --org 123456789012 --out build/org-policies --dry-run   # dryRunSpec: logs, blocks nothing
.venv/bin/landing-zone render-policies --org 123456789012 --out build/org-policies             # spec: enforced
gcloud org-policies set-policy build/org-policies/gcp.resourceLocations.yaml
```

## Test

```bash
make lint           # ruff, ruff format, mypy --strict, import-linter, shellcheck, terraform fmt -check, tflint
make test           # unit tests with coverage (domain + application >= 95%) and the Terraform tests with a mock provider
make test-e2e       # the command-line program as a subprocess over this repository's design files
make validate       # terraform init -backend=false + validate on every module and the environment, an offline plan, checkov
make audit          # pip-audit over the locked dependencies
make check          # lint + test + validate
```

`make up` and `make down` are aliases of `make deploy` and `make teardown` and need the organization.

## Deploy to your own organization

Put the values in `.env` (copy `.env.example`), then:

```bash
scripts/bootstrap.sh        # quota project, billing link, APIs, and the organization roles for you (asks first)
scripts/deploy.sh           # terraform apply: folders, projects, policies and perimeter in DRY RUN, shared VPC, bucket, test identities
scripts/upload-sample.sh    # customers.csv (made-up rows) into the sensitive bucket
scripts/read-dry-run.sh     # step 4: normal traffic, then what the dry-run perimeter WOULD have blocked
scripts/enforce.sh          # steps 2 and 5: flip policies and perimeter to enforced (asks you to confirm you read the logs)
scripts/prove.sh            # steps 2, 3 and 5: refusals, subnets, the two attacks (or run the three prove-/attack scripts one by one)
scripts/teardown.sh         # relax the perimeter, terraform destroy, delete the quota project
```

The lesson's commands, by step, as the scripts run them:

```bash
# step 2 (the gcloud route; Terraform does the same)
gcloud org-policies set-policy build/org-policies-dry-run/iam.disableServiceAccountKeyCreation.yaml
gcloud iam service-accounts keys create /tmp/k.json --iam-account=ANY_SA@dev-app-SUFFIX.iam.gserviceaccount.com   # refused
gcloud storage buckets create gs://dev-app-us-test --project=dev-app-SUFFIX --location=us-central1                # refused
# step 3
gcloud compute shared-vpc enable net-host-SUFFIX
gcloud compute networks subnets add-iam-policy-binding subnet-prod --project=net-host-SUFFIX --region=europe-west1 \
  --member=group:team-prod@example-lab.org --role=roles/compute.networkUser
# step 4
gcloud access-context-manager perimeters dry-run create sensitive_data --policy=$POLICY --perimeter-title="Sensitive data" \
  --perimeter-type=regular --perimeter-resources=projects/$DATA_NUMBER \
  --perimeter-restricted-services=storage.googleapis.com,bigquery.googleapis.com
# step 5
gcloud access-context-manager perimeters dry-run enforce sensitive_data --policy=$POLICY
gcloud storage cp gs://prod-data-sensitive/customers.csv gs://some-bucket-outside-the-perimeter/
```

### Cost

Folders, organization policies, a shared VPC, service accounts and a perimeter are free. What costs money is small and short-lived:

| Resource | Cost |
| --- | --- |
| Projects, folders, organization policies, access policy, perimeter | free |
| Shared VPC network, subnets, firewall rule | free; flow and firewall logs add cents of Cloud Logging when there is traffic |
| Test VMs (`e2-micro`, created and deleted by `prove-network.sh`) | a few minutes each: well under one US cent |
| One tiny bucket and one 5-row file | a fraction of a cent |
| Cloud Identity (free edition) | free |

Expect well under one US dollar for the whole exercise. Check current prices before relying on this. A billing account is still required to create projects with APIs enabled. `scripts/teardown.sh` removes everything Terraform made and schedules the quota project for deletion (30 days to complete, undoable with `gcloud projects undelete`).

## Done when

The lesson's six steps, each with its proof. "Local" runs on this machine now; "needs the organization" means only a real organization can show it, and the command is ready.

| Step | Done when | Proof |
| --- | --- | --- |
| 1 | Every organization policy on the diagram has a reason, and you name one team request it will block. | **Local:** `make design` (`landing-zone check` plus `landing-zone explain`): `OrgPolicy` refuses to exist without a reason and a blocked request, and `explain` prints the table, for example "A developer wants a VM with a public IP address to demo to a customer. Instead: put the demo behind the load balancer." The diagram is in [ARCHITECTURE.md](ARCHITECTURE.md). |
| 2 | Creating a key, a bucket in a disallowed region and a VM with a public IP in a service project are each refused with the policy named. | **Local:** `make simulate` answers each as `REFUSED by org_policy (CONSTRAINT)` with the lesson's message text (`tests/unit/domain/test_landscape.py`). **Needs the organization:** `scripts/enforce.sh`, wait for propagation, then `scripts/prove-policies.sh`, which runs `gcloud iam service-accounts keys create`, `gcloud storage buckets create ... --location=us-central1` and `gcloud compute instances create` with an external address and expects the constraint named in each refusal (plus the uniform-access constraint). |
| 3 | A VM in each service project gets an address from its own subnet, and team A can't create resources in team B's subnet. | **Local:** `terraform test` asserts `networkUser` is bound per subnet to its own team only (`modules/shared-vpc`); a guardrail test fails if the role is granted anywhere else; `make simulate` shows `team-prod ... on team-dev's subnet: REFUSED by shared_vpc_iam (compute.subnetworks.use)`. **Needs the organization:** `scripts/prove-network.sh` creates a private VM in each service project as the test identities, checks the addresses are in 10.50.0.0/24 and 10.60.0.0/24, and expects `compute.subnetworks.use` in the cross-subnet refusals. |
| 4 | The dry-run logs show which legitimate calls would have been blocked, and you add the access levels or ingress rules they need. | **Local:** `landing-zone simulate --mode dry-run` shows `allowed, but dry run would block: NO_MATCHING_ACCESS_LEVEL` and `...RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER`; `terraform test` asserts the perimeter's dry-run configuration (`spec`) exists without the enforced one (`status`). **Needs the organization:** `scripts/read-dry-run.sh` reads the dry-run audit entries; the fix is `office_ip_subnetworks` (an access level) or the project in the perimeter. |
| 5 | Both attempts fail with a VPC Service Controls violation in the logs, though the principal's IAM permissions allow the read. | **Local:** `landing-zone simulate --mode enforced` refuses the copy and the read from outside every access level by `vpc_service_controls`, and refuses a principal with no read role by `iam` instead (so the attack must use a principal that can read). **Needs the organization:** `scripts/enforce.sh`, wait up to 30 minutes, then `scripts/attack.sh` runs both attempts as `data-reader` (which holds `objectViewer`) and expects `vpcServiceControlsUniqueIdentifier` in each error, then reads the violations from the audit log. |
| 6 | The notes include the dry-run step as mandatory and name at least one path the perimeter doesn't cover. | **Local:** [docs/operating-notes.md](docs/operating-notes.md), checked by `tests/unit/test_operating_notes.py`: the exception process, the mandatory dry run, five uncovered paths (an application's own responses, unrestricted services, an insider with an access level, unlisted projects, Terraform itself), and break glass. |

Review checklist from the lesson, mapped: reasons and blocked requests (1), three refusals with the constraint named (2), own subnet and no rights on the other (3), the dry run listed legitimate calls (4), both attacks fail though IAM allows (5), the dry run is mandatory and a gap is named (6), policies and perimeter are code (the YAML files and `infra/`), every change goes through dry run first (the `dry_run` defaults, tested).

## Stretch goals

| Stretch | Built? |
| --- | --- |
| Add a perimeter bridge between two perimeters and show what it allows | Not built; [ARCHITECTURE.md](ARCHITECTURE.md#extending-it) says what to add. |
| Add hierarchical firewall policies at the folder level that teams can't override | Not built; the extension note says where. |
| Export all audit logs to a log bucket in a separate security project with a locked retention policy | Not built; the extension note says where. |

## Project structure

```text
.
├── README.md  ARCHITECTURE.md  CHANGELOG.md  LICENSE
├── Makefile  pyproject.toml  requirements.lock  requirements-dev.lock
├── .env.example  .editorconfig  .shellcheckrc  .checkov.yaml
├── .github/workflows/ci.yml        python (lint, tests, design, simulate, audit) and terraform
├── design/                         landing-zone.yaml (the slice), scenarios.yaml (the lesson's requests and their answers)
├── policies/org-policies.yaml      the four policies with reason and blocked request
├── data/customers.csv              five made-up rows
├── src/landing_zone/
│   ├── domain/                     Design, OrgPolicy, requests, Landscape (the decision rules), Decision; imports nothing else
│   ├── application/                check, render, scenarios; imports domain
│   ├── infrastructure/             yaml_files.py (read the YAML, write policy documents); imports application, domain
│   └── interfaces/                 the landing-zone command; imports all below
├── tests/
│   ├── unit/                       domain, application, infrastructure, interfaces, Terraform guardrails, operating notes
│   └── e2e/                        the program as a subprocess over the real design files
├── infra/
│   ├── .tflint.hcl
│   ├── modules/                    folders, project, org-policies, shared-vpc, perimeter, sensitive-bucket, lab-identities
│   └── environments/lab/           main.tf, variables.tf, outputs.tf, lab.tfvars.example, tests/
├── scripts/                        bootstrap, deploy, render-policies, upload-sample, prove-*, read-dry-run, enforce, attack, teardown
├── tech/                           33 technology notes and an index (README.md)
└── docs/                           operating-notes.md, adr/
```

Dependency rule: `interfaces` -> `infrastructure` -> `application` -> `domain`, never upward; `domain` and `application` may not import `pathlib`, `yaml`, `json`, `argparse` or `subprocess`. Both rules run in `make lint` through import-linter.

## What is simplified for teaching

- One environment (`lab`), local state, one operator, no pipeline; a real landing zone splits stacks and applies each from a pipeline.
- The access level is one IP range; production uses device and identity conditions and ingress and egress rules.
- The lab identities hold project-level `compute.instanceAdmin.v1` so a test VM can be created; they are deleted with the lab.
- The simulator models the lesson's four constraints, the subnet rule and two violation reasons; it is a teaching aid, not an implementation of the services.
- There is no `sql/` folder: no database is involved.

## Verification record

Last verified on 2026-10-27 on macOS with Python 3.13, Terraform 1.17.0, tflint 0.65.0 (ruleset google 0.41.0), checkov 3.3.30. From a fresh clone: `make install`, `make check` (98 unit tests, lint, types, import rules, shellcheck, Terraform format, tflint, 8 module and environment validations, the offline plan of 50 resources, the Terraform tests, checkov), `make test-e2e` (3 tests), `make design` and `make simulate` passed; `make audit` found no known vulnerabilities. Not verified: any behavior against a real organization, including the exact wording of the audit log filters in `scripts/read-dry-run.sh` and `scripts/attack.sh`.

## License

MIT, Copyright (c) 2026 Sumit Srivastava. See [LICENSE](LICENSE).
