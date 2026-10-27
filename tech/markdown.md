# Markdown

## 1. What it is

Markdown is a way of writing formatted text in a plain text file. You type ordinary characters and a few marks, and a program turns them into headings, lists, tables, links and code blocks. A file ending in `.md` is a Markdown file. GitHub shows `README.md` below the file list of a repository, formatted. The dialect used here is GitHub Flavored Markdown, which adds tables and fenced code blocks to the original.

## 2. Why this repository uses it

A repository has to explain itself. The lesson asks for a README with run, test and deploy instructions, an architecture document with a diagram, a record of each decision, and operating notes. All of it is Markdown, so it lives next to the code, is reviewed with the code, and changes in the same commit. Some of it is tested like code: a test reads `docs/operating-notes.md` and fails if a required heading is missing.

## 3. Where it appears

| Path | What it is |
| --- | --- |
| `README.md` | The front page: what the project is, how to run, test and deploy it, the "Done when" table, the project structure, what is simplified, the verification record. |
| `ARCHITECTURE.md` | The components, the hierarchy diagram (see `mermaid.md`), the pattern, trade-offs, failure modes and limits. |
| `CHANGELOG.md` | What changed in each version. |
| `docs/adr/000N-*.md` | Architecture decision records: one decision each, with context, the decision and the consequences. |
| `docs/operating-notes.md` | Step 6 of the lesson: exceptions, testing a change, what the perimeter does not cover, break glass. |
| `infra/modules/*/README.md`, `infra/environments/lab/README.md` | One page per Terraform module: inputs, outputs, example, tests. |
| `tech/*.md` | These notes. |

## 4. How it works underneath

A Markdown file is just text. A renderer (GitHub, an editor preview) reads it line by line and applies the rules. Nothing is run; there are no variables or loops. The marks used in this repository:

- `#`, `##`, `###` at the start of a line make headings of decreasing size. The text after the marks is the title. A blank line separates paragraphs.
- `-` or `*` at the start of a line makes a bullet; `1.` makes a numbered item. Indenting nests a list.
- `**bold**` is bold. Backticks make `code` inside a sentence.
- Three backticks on a line of their own start a **fenced code block**, three more end it. The word after the opening backticks (for example `bash`) names the language, for colors. Inside, nothing is formatted.
- `[text](address)` is a link. The address can be a file in the repository (`ARCHITECTURE.md`) or a web address. `#name` after a file name jumps to a heading.
- A **table** has a header row of cells between `|`, a divider row `| --- | --- |`, then rows. A `|` inside a cell must be written `\|`.
- A line with only `---` is a horizontal rule.

## 5. Walkthrough of this repository's use

### The README's table at the top

`README.md`

```markdown
| **Lesson** | `/prep/gcp/project-landing-zone-slice`, "Build a landing-zone slice with a perimeter" (`data-structure-explainer/src/content/tracks/gcp/17-project-landing-zone-slice.md` in the Plainround app) |
| **Planned hours** | 14 |
| **Level** | Advanced |
| **Architecture** | [ARCHITECTURE.md](ARCHITECTURE.md), decisions in [docs/adr](docs/adr), operating notes in [docs/operating-notes.md](docs/operating-notes.md) |
| **Author** | Sumit Srivastava |
```

A two-column table with an empty header row (`| | |`), then the divider `| --- | --- |`, then one row per fact. Each row is a fact (lesson, planned hours, level, architecture, author) with `**bold**` labels and links.

### Headings in a fixed order

The README's second-level headings (`##`) are, in order: What is here, Prerequisites, Run it on this machine, Test, Deploy to your own organization, Done when, Stretch goals, Project structure, What is simplified for teaching, Verification record, License. The order is a repository rule (`TEMPLATE.md`), so every project reads the same.

### A fenced block with a diagram of the folders

The "Project structure" section is a fence with the language `text`: a drawing made of the characters `├──`, `│` and `└──`, which only line up in a fixed-width font. That is why it is in a code block.

### A module README

`infra/modules/perimeter/README.md`

```markdown
# perimeter

An access policy (or an existing one), access levels from address ranges, and a VPC Service Controls perimeter whose dry-run configuration (`spec`) is always written and whose enforced configuration (`status`) is written only when `mode = "enforced"`.

Used for: Steps 4 and 5 (dry-run the perimeter, enforce and attack).

## Inputs

| Name | Description | Type | Default |
| --- | --- | --- | --- |
| `organization` | organizations/ID, the parent of the access policy. | `string` | required |
| `access_policy_id` | Id (the number) of the organization's existing access policy. Empty creates one. | `string` | `""` |
| `name` | Perimeter name: letters, digits and underscores. | `string` | required |
| `title` | Human-readable title. | `string` | required |
| `project_numbers` | Numbers of the projects inside the perimeter. | `list(string)` | required |
| `restricted_services` | Services the perimeter restricts, for example storage.googleapis.com. | `list(string)` | required |
| `access_levels` | Access level name => IP ranges whose callers count as trusted. | `map(list(string))` | `{}` |
| `access_level_names` | Names of the access levels the perimeter accepts (a subset of access_levels). | `list(string)` | `[]` |
| `mode` | dry_run logs what the perimeter would block; enforced blocks it. Always run dry_run first. | `string` | `"dry_run"` |

## Outputs

| Name | Description |
| --- | --- |
| `access_policy_id` | Id of the access policy the perimeter belongs to. |
| `perimeter_name` | Full resource name of the perimeter. |
| `mode` | dry_run or enforced. |

## Example

See `infra/environments/lab/main.tf`, which composes this module.

## Tests

yes (`tests/*.tftest.hcl`, mock provider). Run `make test-terraform` from the repository root.
```

- `# perimeter` is the title; the first paragraph says what the module is.
- "Used for:" ties the module to the lesson's steps.
- `## Inputs` and `## Outputs` are tables with the same columns as the Terraform variables and outputs files (see `terraform.md`): name in backticks, description, type, default.
- `## Example` points to the environment that uses the module; `## Tests` says how to run them.

### The other module pages and the environment page

They follow the same shape as the perimeter's page. Each one in full:

`infra/modules/folders/README.md`

```markdown
# folders

Creates the folders under the organization.

Used for: Step 1 (the hierarchy).

## Inputs

| Name | Description | Type | Default |
| --- | --- | --- | --- |
| `parent` | Parent of every folder: organizations/ID or folders/ID. | `string` | required |
| `names` | Display names of the folders to create. | `list(string)` | required |
| `deletion_protection` | Refuse to delete the folders. False for a lab so the teardown works. | `bool` | `false` |

## Outputs

| Name | Description |
| --- | --- |
| `ids` | Folder name => folder id (the number only). |
| `names` | Folder name => resource name (folders/ID), the form parents take. |

## Example

See `infra/environments/lab/main.tf`, which composes this module.

## Tests

yes (`tests/*.tftest.hcl`, mock provider). Run `make test-terraform` from the repository root.
```

`infra/modules/project/README.md`

```markdown
# project

A project in a folder with billing, no default network, labels and its APIs.

Used for: Steps 1 and 3 (the four projects).

## Inputs

| Name | Description | Type | Default |
| --- | --- | --- | --- |
| `name` | Display name, also the lesson's project name. | `string` | required |
| `project_id` | Globally unique project id (6-30 characters). | `string` | required |
| `folder_id` | Folder the project lives in (the number only). | `string` | required |
| `billing_account` | Billing account id. | `string` | required |
| `services` | APIs to enable. | `list(string)` | `[]` |
| `labels` | Labels for the project. | `map(string)` | `{}` |
| `deletion_policy` | PREVENT, ABANDON or DELETE. DELETE in a lab so terraform destroy schedules the project for deletion. | `string` | `"DELETE"` |

## Outputs

| Name | Description |
| --- | --- |
| `project_id` | Project id. |
| `number` | Project number. |

## Example

See `infra/environments/lab/main.tf`, which composes this module.

## Tests

yes (`tests/*.tftest.hcl`, mock provider). Run `make test-terraform` from the repository root.
```

`infra/modules/org-policies/README.md`

```markdown
# org-policies

Organization policies from the policy file. Every policy gets a dry-run spec; the enforced spec is written only when `mode = "enforced"`, so a change is logged before it blocks anything.

Used for: Step 2 (organization policies, dry run first).

## Inputs

| Name | Description | Type | Default |
| --- | --- | --- | --- |
| `organization` | organizations/ID, the parent of organization-level policies. | `string` | required |
| `folder_parents` | Folder name => folders/ID, for policies set at folder level. | `map(string)` | `{}` |
| `mode` | dry_run writes only the dry-run spec (violations are logged, nothing is blocked); enforced also writes the real spec. | `string` | `"dry_run"` |
| `policies` | The policy entries of policies/org-policies.yaml. | `list(object({ constraint = string kind = string enforce = optional(bool, false) allowed_values = optional(list(string), []) deny_all = optional(bool, false) folder = optional(string) }))` | required |

## Outputs

| Name | Description |
| --- | --- |
| `constraints` | Constraint@level of every policy managed here. |
| `mode` | dry_run or enforced. |

## Example

See `infra/environments/lab/main.tf`, which composes this module.

## Tests

yes (`tests/*.tftest.hcl`, mock provider). Run `make test-terraform` from the repository root.
```

`infra/modules/lab-identities/README.md`

```markdown
# lab-identities

Three service accounts without keys that stand in for a team-prod member, a team-dev member and a principal who can read the sensitive data; the operator may impersonate them.

Used for: Steps 3 and 5 (prove the subnet rules and attack as a principal with valid read access).

## Inputs

| Name | Description | Type | Default |
| --- | --- | --- | --- |
| `prod_app_project_id` | Project id of prod-app. | `string` | required |
| `dev_app_project_id` | Project id of dev-app. | `string` | required |
| `data_project_id` | Project id of prod-data. | `string` | required |
| `operator_member` | Who may impersonate the test identities, for example user:you@example-lab.org. | `string` | required |

## Outputs

| Name | Description |
| --- | --- |
| `team_prod_member` | IAM member of the team-prod test identity. |
| `team_dev_member` | IAM member of the team-dev test identity. |
| `data_reader_member` | IAM member of the data reader. |
| `emails` | Emails of the three test identities. |

## Example

See `infra/environments/lab/main.tf`, which composes this module.

## Tests

yes (`tests/*.tftest.hcl`, mock provider). Run `make test-terraform` from the repository root.
```

`infra/modules/shared-vpc/README.md`

```markdown
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
```

`infra/modules/sensitive-bucket/README.md`

```markdown
# sensitive-bucket

A private, uniform-access, versioned bucket in an EU location, readable by the listed members only.

Used for: Step 5 (the data the perimeter protects).

## Inputs

| Name | Description | Type | Default |
| --- | --- | --- | --- |
| `project_id` | Project that owns the bucket. | `string` | required |
| `name` | Globally unique bucket name. | `string` | required |
| `location` | Bucket location; the organization policy only allows EU locations. | `string` | required |
| `viewer_members` | Members that may read objects in this bucket, keyed by a fixed label. | `map(string)` | `{}` |
| `force_destroy` | Delete the bucket even when it holds objects. True only for a lab. | `bool` | `false` |
| `labels` | Labels for the bucket. | `map(string)` | `{}` |

## Outputs

| Name | Description |
| --- | --- |
| `name` | Bucket name. |
| `viewer_members` | Members granted objectViewer. |

## Example

See `infra/environments/lab/main.tf`, which composes this module.

## Tests

yes (`tests/*.tftest.hcl`, mock provider). Run `make test-terraform` from the repository root.
```

`infra/environments/lab/README.md`

```markdown
# lab environment

The composition for the landing-zone slice: folders, projects, organization policies, the shared VPC, the sensitive bucket, the test identities and the perimeter, built from `design/landing-zone.yaml` and `policies/org-policies.yaml`. Every module is in `../../modules`.

## Variables

See `variables.tf`; `lab.tfvars.example` shows every value with placeholders. `scripts/deploy.sh` writes the real `lab.tfvars` from `.env` (git-ignored). `policy_mode` and `perimeter_mode` both default to `dry_run`; `scripts/enforce.sh` flips them. `quota_project_id` is a project that already exists (`scripts/bootstrap.sh` creates it).

## Validate without credentials

```bash
cd infra/environments/lab
terraform init -backend=false
terraform validate
GOOGLE_OAUTH_ACCESS_TOKEN=offline-placeholder terraform plan -var-file=lab.tfvars.example   # 50 resources to add, no API call
terraform test                                                                             # the design, the modes, the names
```

The offline plan works because nothing in the configuration reads from Google Cloud: the design comes from the YAML files, and no data source is used.

## Enforcing and tearing down

Enforcing the perimeter also stops Terraform, run from an address outside the `office` access level, from reading the bucket. That is the perimeter working. After enforcement use `terraform apply -refresh=false`, or set `office_ip_subnetworks` to your address first. `scripts/teardown.sh` relaxes the perimeter with a targeted `-refresh=false` apply, waits, then destroys.

## Outputs

`project_ids`, `project_numbers`, `folders`, `policy_constraints`, `policy_mode`, `subnet_cidrs`, `perimeter`, `access_policy_id`, `sensitive_bucket`, `test_identities`.

## State

Local. For shared use copy `backend.tf.example` to `backend.tf`, create the bucket (versioning on) and run `terraform init -migrate-state`.
```

The pages differ only in their title, the one-line description, the step they serve, and the rows of the two tables. The environment's page lists its own inputs and outputs and how to run it.

### An architecture decision record

`docs/adr/0002-dry-run-is-the-default-for-policies-and-the-perimeter.md`

```markdown
# 2. Dry run is the default for every policy and the perimeter

Status: accepted, 2026-10-27

## Context

An organization policy refuses creations that were allowed yesterday, and a VPC Service Controls perimeter refuses calls that IAM allows. The lesson says every change goes through dry-run mode first, "as a real platform team would do".

## Decision

`modules/org-policies` always writes `dry_run_spec` and writes `spec` only when `mode = "enforced"`. `modules/perimeter` sets `use_explicit_dry_run_spec = true`, always writes `spec` (the dry-run configuration) and writes `status` (the enforced configuration) only when `mode = "enforced"`. The environment's `policy_mode` and `perimeter_mode` default to `dry_run`. `scripts/enforce.sh` asks for confirmation that the logs were read. Tests assert each default and each switch.

## Consequences

- The first `terraform apply` of a new organization blocks nothing.
- Enforcement is a one-variable change that appears in a pull request and in the plan.
- A dry-run perimeter only logs, so the proofs of steps 2 and 5 need the enforced mode and up to 30 minutes of propagation.
- After enforcement, Terraform from an address outside the access level cannot read the bucket; the teardown relaxes the perimeter first.
```

An ADR is short and always has the same parts: a numbered title, a status and date, **Context** (the problem), **Decision** (what was chosen) and **Consequences**. The number never changes, so other documents can refer to "ADR 2".

### A document that is also tested

`tests/unit/test_operating_notes.py`

```python
    for heading in (
        "## How a team requests an exception",
        "## How a change is tested (the dry run is mandatory)",
        "## What the perimeter does not protect against",
        "## Break glass",
    ):
        assert heading in NOTES
```

The test searches the file for the exact heading lines. A heading renamed by accident, or removed, fails the build.

## 6. Try it yourself

```bash
grep -n "^## " README.md
```
Expected: the eleven second-level headings of the README, with line numbers.

```bash
ls docs/adr
```
Expected: `0001-the-design-and-the-policies-are-data.md`, `0002-dry-run-is-the-default-for-policies-and-the-perimeter.md`, `0003-a-simulator-for-the-decision-rules.md`.

```bash
.venv/bin/python -m pytest tests/unit/test_operating_notes.py -q -p no:cacheprovider
```
Expected: `3 passed`.

```bash
grep -c '^| ' infra/modules/perimeter/README.md
```
Expected: the number of table rows in the perimeter module's page (headers and dividers included).

```bash
grep -rn "](" README.md | grep -o "](\([^)]*\))" | head -3
```
Expected: the first three link targets, for example `(ARCHITECTURE.md)`.

## 7. Mistakes people make

- **A missing blank line** before a list or table, so the renderer shows plain text.
- **A `|` inside a table cell** without a backslash, which splits the cell.
- **Tabs and spaces mixed** in nested lists.
- **Documents that drift from the code.** Here tests check the parts that matter, and the `tech/` notes quote the code itself.
- **Absolute web links to files in the same repository.** Relative links keep working in a fork or a clone.
- **A fence that is never closed.** The rest of the page turns into code.

## 8. Check yourself

1. What marks a heading? *`#` characters at the start of a line.*
2. How do you write a code block? *Three backticks before and after, with the language after the first three.*
3. How do you put a `|` in a table cell? *Write `\|`.*
4. What are the four parts of an ADR? *Title with status and date, Context, Decision, Consequences.*
5. How does this repository stop a required heading from disappearing? *A test searches the file for it.*

## 9. Further reading

- GitHub Flavored Markdown specification: <https://github.github.com/gfm/>
- Basic writing and formatting syntax: <https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax>
- Architecture decision records: <https://adr.github.io/>
