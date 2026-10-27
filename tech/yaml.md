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
