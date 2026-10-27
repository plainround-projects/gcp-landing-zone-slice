# YAML

## 1. What it is

YAML is a plain-text format for structured data, designed to be easy for people to read. It has three building blocks: **mappings** (`key: value` pairs), **sequences** (lists, one `- item` per line) and **scalars** (text, numbers, `true`/`false`, `null`). **Indentation with spaces** shows nesting; tabs are not allowed. Lines starting with `#` are comments. YAML also has a compact **flow style**: `[a, b]` is a list and `{x: 1, y: 2}` a mapping on one line.

## 2. Why this repository uses it

In this repository YAML is the **source of truth** for the design and the rules. Three files describe the landing zone as data, and two programs read the same files: the Python tool (checks and simulates) and Terraform (builds). Because both read one file, they cannot drift apart. The GitHub workflow and the checkov configuration are YAML too, because those tools demand it.

## 3. Where it appears

| Path | What it holds |
| --- | --- |
| `design/landing-zone.yaml` | The folders, projects, shared VPC, perimeter, access level and sensitive data. |
| `policies/org-policies.yaml` | The four organization policies, each with a reason and the request it blocks. |
| `design/scenarios.yaml` | The 13 requests the lesson makes and the answer the landing zone must give. |
| `.github/workflows/ci.yml` | The CI jobs (see `github-actions.md`). |
| `.checkov.yaml` | Which scanners to run (see `checkov.md`). |
| `build/org-policies*/*.yaml` | Generated, not committed: the documents `landing-zone render-policies` writes for `gcloud`. |

## 4. How it works underneath

A program reads the text and builds data in memory: a mapping becomes a dictionary, a sequence a list. The indentation is the structure, so one wrong space changes the meaning. A key is separated from its value by a colon **followed by a space**: `group:team-dev@example-lab.org` has a colon with no space after it, so it is one piece of text, not a key and a value.

Parsers also guess types, and they do not guess alike. PyYAML follows YAML 1.1: bare `no`, `yes` and `on` become booleans and `22:22` becomes the number 1342. Terraform's `yamldecode` still turns `no` and `on` into booleans but keeps `22:22` as text (checked with Terraform 1.17.0). The safe habit is the same for both: **quote any value that must stay text**.

`null` (also `~` or an empty value) means "nothing". A scenario with `from_access_level: null` says the caller's address matches no access level.

## 5. Walkthrough of this repository's use

The design file lists projects as a sequence of mappings:

`design/landing-zone.yaml`

```yaml
projects:
  - name: prod-data
    folder: production
    role: data
  - name: prod-app
    folder: production
    role: service
  - name: dev-app
    folder: non-production
    role: service
  - name: net-host
    folder: shared
    role: host
```

- `projects:` is a key; its value is a sequence. Each item starts with `- ` and is a mapping with three keys.
- `role: data` is a **string** (`data`). Python turns it into the enum `ProjectRole.DATA`; Terraform picks the list of APIs to enable with `local.services[each.value.role]`.
- Names such as `prod-data` need no quotes; they are plain text.

Comments explain a value where it is set:

`design/landing-zone.yaml`

```yaml
access_levels:
  - name: office
    # 203.0.113.0/24 is a documentation range. Put your own office or home address here (a /32 is enough).
    ip_subnetworks:
      - 203.0.113.0/24
```

The comment says that `203.0.113.0/24` is a documentation range to be replaced. A list of one item is still written with a dash.

The policy file shows nested mappings and long text:

`policies/org-policies.yaml`

```yaml
  - constraint: iam.disableServiceAccountKeyCreation
    kind: boolean
    enforce: true
    level: organization
    reason: A downloaded key is a password that never expires and cannot be tied to a person; workloads use the platform's short-lived credentials.
    blocks:
      request: A developer wants to download a key for a service account to run a script from a laptop.
      instead: Impersonate the service account with their own identity, or use workload identity federation.
```

- `enforce: true` is a boolean. `kind: boolean` is a string that happens to name a kind.
- `reason:` holds a sentence as a plain scalar on one line. A plain scalar may contain commas, apostrophes and semicolons; it must not contain a colon followed by a space.
- `blocks:` is a mapping inside a mapping, indented by two more spaces.

The scenarios use flow style, one line per request:

`design/scenarios.yaml`

```yaml
scenarios:
  - name: create a service account key in dev-app
    request: { type: create_service_account_key, project: dev-app }
    expect: { allowed: false, control: org_policy, detail: iam.disableServiceAccountKeyCreation }
```

`request: { type: create_service_account_key, project: dev-app }` is a mapping on one line. Lists of text inside it are quoted: `caller_groups: ["group:team-dev@example-lab.org"]`.

The CI workflow:

`.github/workflows/ci.yml`

```yaml
jobs:
  python:
    name: Format, lint, types, import rules, unit and end-to-end tests with coverage, design check, dependency audit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: make lint-python test-python test-e2e design simulate
      - run: make audit
```

`python:` is a job name; under `steps:` each item begins with `- ` and is a mapping (`uses:`, `with:` or `run:`). A key named `on:` at the top of the workflow trips YAML 1.1 parsers, which read it as the boolean `true`; GitHub's own reader accepts it.

## Every YAML file, whole

### `design/landing-zone.yaml`

`design/landing-zone.yaml`

```yaml
# The landing-zone slice as data. Terraform (infra/environments/lab) builds it; the landing-zone tool checks it and
# simulates requests against it. Names are the lesson's; Terraform appends a suffix to project ids and bucket names
# because both are global.
organization:
  domain: example-lab.org

folders:
  - name: production
  - name: non-production
  - name: shared

projects:
  - name: prod-data
    folder: production
    role: data
  - name: prod-app
    folder: production
    role: service
  - name: dev-app
    folder: non-production
    role: service
  - name: net-host
    folder: shared
    role: host

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

sensitive_data:
  project: prod-data
  bucket: prod-data-sensitive
  object: customers.csv
```

- The first three lines are comments. `organization.domain` is the domain of the organization (an example domain, so nothing real is named).
- `folders` is a list of mappings with a `name`; `projects` lists each project's `name`, `folder` and `role`.
- `shared_vpc`: `host_project`, `network`, `region`, then `subnets`, each with its `cidr` (a range, see `ipaddress-and-cidr.md`), the `service_project` that uses it and the `user_groups` (a list of groups written `group:EMAIL`).
- `perimeter`: `name` and `title` (the machine name and the human title), the `projects` inside, the `restricted_services` (Google API names ending in `.googleapis.com`) and the `access_levels` it accepts by name.
- `access_levels` (top level): each has a `name` and `ip_subnetworks`, a list of ranges; the comment says why `203.0.113.0/24` is only a documentation range.
- `sensitive_data`: the `project`, the `bucket` (without the suffix) and the `object`.
- Terraform reads the file with `yamldecode`; Python reads it with PyYAML. The keys are the same names in both programs.

### `policies/org-policies.yaml`

`policies/org-policies.yaml`

```yaml
# The organization policies, one entry each, with the reason and the team request it blocks (step 1 asks for both).
# Terraform reads this file (infra/modules/org-policies); `landing-zone render-policies` turns it into the YAML that
# `gcloud org-policies set-policy` takes.
policies:
  - constraint: iam.disableServiceAccountKeyCreation
    kind: boolean
    enforce: true
    level: organization
    reason: A downloaded key is a password that never expires and cannot be tied to a person; workloads use the platform's short-lived credentials.
    blocks:
      request: A developer wants to download a key for a service account to run a script from a laptop.
      instead: Impersonate the service account with their own identity, or use workload identity federation.

  - constraint: gcp.resourceLocations
    kind: list
    allowed_values:
      - in:eu-locations
    level: organization
    reason: The data must stay in the EU, and a location list is much easier to enforce at creation than to audit afterwards.
    blocks:
      request: A team wants a bucket in us-central1 because a tool they like defaults to it.
      instead: Use an EU location (europe-west1), or ask for an exception on one folder, recorded in this file.

  - constraint: storage.uniformBucketLevelAccess
    kind: boolean
    enforce: true
    level: organization
    reason: Per-object ACLs make "who can read this bucket" unanswerable from the bucket's IAM policy alone.
    blocks:
      request: A developer wants to share one object publicly by setting an object ACL.
      instead: Grant a role on the bucket, or hand out a signed URL for that one object.

  - constraint: compute.vmExternalIpAccess
    kind: list
    deny_all: true
    level: organization
    reason: No VM may be reachable from the internet by accident; public entry points are load balancers, which are reviewed.
    blocks:
      request: A developer wants a VM with a public IP address to demo to a customer.
      instead: Put the demo behind the load balancer, which has the public address; the VM stays private.
```

- Each entry has `constraint`, `kind`, `level` and a `reason`, plus the fields of its kind: `enforce: true` for a boolean; `allowed_values` (a list) or `deny_all: true` for a list policy.
- `blocks` is a mapping with `request` (a request from the team that this policy refuses) and `instead` (what the team should do). The lesson asks for both on every policy.
- Entries are separated by a blank line only for reading; YAML ignores blank lines.

### `design/scenarios.yaml`: the 13 requests

`design/scenarios.yaml`

```yaml
# Requests the lesson makes in steps 2, 3 and 5, with what the landing zone must answer. `landing-zone simulate` runs
# them against design/landing-zone.yaml and policies/org-policies.yaml and fails when an answer differs.
scenarios:
  - name: create a service account key in dev-app
    request: { type: create_service_account_key, project: dev-app }
    expect: { allowed: false, control: org_policy, detail: iam.disableServiceAccountKeyCreation }

  - name: create a bucket in us-central1 in dev-app
    request: { type: create_bucket, project: dev-app, location: us-central1, uniform_access: true }
    expect: { allowed: false, control: org_policy, detail: gcp.resourceLocations }

  - name: create a bucket in europe-west1 in dev-app
    request: { type: create_bucket, project: dev-app, location: europe-west1, uniform_access: true }
    expect: { allowed: true }

  - name: create a bucket with per-object ACLs in dev-app
    request: { type: create_bucket, project: dev-app, location: europe-west1, uniform_access: false }
    expect: { allowed: false, control: org_policy, detail: storage.uniformBucketLevelAccess }

  - name: create a VM with a public address in dev-app
    request: { type: create_vm, project: dev-app, zone: europe-west1-b, subnet: subnet-dev, external_ip: true, caller_groups: ["group:team-dev@example-lab.org"] }
    expect: { allowed: false, control: org_policy, detail: compute.vmExternalIpAccess }

  - name: create a private VM in dev-app on subnet-dev as team-dev
    request: { type: create_vm, project: dev-app, zone: europe-west1-b, subnet: subnet-dev, external_ip: false, caller_groups: ["group:team-dev@example-lab.org"] }
    expect: { allowed: true }

  - name: team-prod creates a VM in prod-app on subnet-prod
    request: { type: create_vm, project: prod-app, zone: europe-west1-b, subnet: subnet-prod, external_ip: false, caller_groups: ["group:team-prod@example-lab.org"] }
    expect: { allowed: true }

  - name: team-prod creates a VM in prod-app on team-dev's subnet
    request: { type: create_vm, project: prod-app, zone: europe-west1-b, subnet: subnet-dev, external_ip: false, caller_groups: ["group:team-prod@example-lab.org"] }
    expect: { allowed: false, control: shared_vpc_iam, detail: compute.subnetworks.use }

  - name: a reader copies customers.csv to a bucket outside the organization
    request: { type: copy_object, caller_can_read: true, source_project: prod-data, destination_project: outside-the-organization }
    expect: { allowed: false, control: vpc_service_controls, detail: RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER }

  - name: a reader copies customers.csv to another bucket inside the perimeter
    request: { type: copy_object, caller_can_read: true, source_project: prod-data, destination_project: prod-data }
    expect: { allowed: true }

  - name: a reader reads customers.csv from a laptop that matches no access level
    request: { type: read_object, caller_can_read: true, project: prod-data, from_access_level: null }
    expect: { allowed: false, control: vpc_service_controls, detail: NO_MATCHING_ACCESS_LEVEL }

  - name: a reader reads customers.csv from the office access level
    request: { type: read_object, caller_can_read: true, project: prod-data, from_access_level: office }
    expect: { allowed: true }

  - name: a principal without a read role reads customers.csv from the office
    request: { type: read_object, caller_can_read: false, project: prod-data, from_access_level: office }
    expect: { allowed: false, control: iam, detail: storage.objects.get }
```

Each scenario has `name`, `request` and `expect`. `request.type` chooses the kind of request; the other keys are that kind's fields (see `requests.py` in `python.md`). `expect.allowed` says whether the request should succeed; for a refusal, `control` names the control that stops it and `detail` the constraint, permission or reason.

1. A service account key in `dev-app`: refused by `org_policy`, `iam.disableServiceAccountKeyCreation`.
2. A bucket in `us-central1`: refused by `org_policy`, `gcp.resourceLocations`.
3. A bucket in `europe-west1`: allowed.
4. A bucket with per-object ACLs (`uniform_access: false`): refused by `storage.uniformBucketLevelAccess`.
5. A VM with `external_ip: true`: refused by `compute.vmExternalIpAccess`. The caller is in the team-dev group, so the subnet check is not what refuses it.
6. A private VM in `dev-app` on `subnet-dev` as team-dev: allowed.
7. team-prod creating a VM on `subnet-prod`: allowed.
8. team-prod on `subnet-dev`: refused by `shared_vpc_iam`, `compute.subnetworks.use`.
9. A reader (`caller_can_read: true`) copying `customers.csv` from `prod-data` to `outside-the-organization`: refused by `vpc_service_controls`, `RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER`.
10. The same copy to `prod-data` (inside): allowed.
11. A read from a laptop that matches no access level (`from_access_level: null`): refused with `NO_MATCHING_ACCESS_LEVEL`.
12. A read from the `office` access level: allowed.
13. A caller without a read role (`caller_can_read: false`), even from the office: refused by `iam`, `storage.objects.get`.

The flow-style mappings `{ type: ..., project: ... }` are one line each. A list inside one is quoted: `["group:team-dev@example-lab.org"]`.

### `.github/workflows/ci.yml`

`.github/workflows/ci.yml`

```yaml
name: ci

on: [push, pull_request]

permissions:
  contents: read

jobs:
  python:
    name: Format, lint, types, import rules, unit and end-to-end tests with coverage, design check, dependency audit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: make lint-python test-python test-e2e design simulate
      - run: make audit

  terraform:
    name: Terraform format, tflint, validate, offline plan, policy tests, checkov
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.17.0"
          terraform_wrapper: false
      - uses: terraform-linters/setup-tflint@v4
        with:
          tflint_version: v0.65.0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install checkov==3.3.30
      - run: make lint-terraform test-terraform validate
```

- `name: ci` names the workflow. `on: [push, pull_request]` starts it on every push and every pull request.
- `permissions: contents: read` gives the workflow's token read access to the repository and nothing else (least privilege).
- Under `jobs:` there are two jobs, `python` and `terraform`; they run at the same time, each on a fresh Ubuntu machine (`runs-on: ubuntu-latest`).
- Each `steps` item is either `uses:` (a ready-made action, with `with:` for its inputs) or `run:` (a shell command). `actions/checkout@v4` copies the repository onto the machine; `actions/setup-python@v5` installs Python 3.12; `hashicorp/setup-terraform@v3` installs Terraform 1.17.0 with `terraform_wrapper: false` (so the plain `terraform` command is used and its output is not rewrapped); `terraform-linters/setup-tflint@v4` installs tflint `v0.65.0`; `pip install checkov==3.3.30` installs checkov at a fixed version.
- The `run:` lines call `make` targets, so CI runs exactly what you run (see `github-actions.md`).

### `.checkov.yaml`

The whole file was quoted and explained in `checkov.md`.

## 6. Try it yourself

```bash
.venv/bin/landing-zone check
```
Expected: `ok: the design and the policies are consistent` (both YAML files parsed and passed every check).

```bash
.venv/bin/python -c "
import yaml
d = yaml.safe_load(open('design/landing-zone.yaml'))
print([p['name'] for p in d['projects']]); print(d['shared_vpc']['subnets'][0]['user_groups'])"
```
Expected: `['prod-data', 'prod-app', 'dev-app', 'net-host']` then `['group:team-prod@example-lab.org']`.

```bash
.venv/bin/python -c "
import yaml
print(yaml.safe_load('r: { allowed: false, control: iam }'))"
```
Expected: `{'r': {'allowed': False, 'control': 'iam'}}`

```bash
.venv/bin/python -c "
import yaml
print(yaml.safe_load('x: null\ny:\nz: \"null\"'))"
```
Expected: `{'x': None, 'y': None, 'z': 'null'}`. An empty value and `null` both mean nothing; the quoted `"null"` is the four-letter text.

```bash
.venv/bin/python -c "
import yaml
try:
    yaml.safe_load('a:\n\t- b')
except yaml.YAMLError as error:
    print(type(error).__name__)"
```
Expected: `ScannerError` (a tab used for indentation is not allowed).

## 7. Mistakes people make

- **Tabs for indentation.** Not allowed.
- **Inconsistent indentation** moving a key to the wrong parent.
- **Unquoted special values** (`yes`, `no`, `on`, `1.10`, `22:22`, version numbers). Quote them.
- **A colon followed by a space inside a plain value.** It starts a new mapping; quote the value.
- **Confusing a string with a list** (`command: a b` against `command: [a, b]`). Check what the reader expects.
- **Two copies of the truth.** The Terraform tests repeat the subnet ranges and project ids as literals; a Python test (`test_the_terraform_test_literals_match_the_design_file`) fails when the design changes and the literals do not.

## 8. Check yourself

1. What shows nesting in YAML? *Indentation with spaces.*
2. How do you write a list item? *A line starting with `- `.*
3. Why is `group:team-dev@example-lab.org` one piece of text? *The colon has no space after it, so it does not separate a key from a value.*
4. What does `from_access_level: null` mean? *No value: the caller matches no access level.*
5. Why do Terraform and the Python tool read the same file? *So the build and the checks cannot disagree.*

## 9. Further reading

- YAML 1.2 specification: <https://yaml.org/spec/1.2.2/>
- YAML 1.1 specification: <https://yaml.org/spec/1.1/>
- Terraform `yamldecode`: <https://developer.hashicorp.com/terraform/language/functions/yamldecode>
- Workflow syntax: <https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions>
