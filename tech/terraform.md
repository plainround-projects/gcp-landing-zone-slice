# Terraform (and its HCL language)

## 1. What it is

Terraform is a command-line tool that builds cloud infrastructure from text files. You **describe** what should exist (a folder, a project, an organization policy, a bucket) in files written in **HCL** (HashiCorp Configuration Language), and Terraform works out what to create, change or delete to make reality match. A **provider** is a plug-in that knows one platform's API; here `hashicorp/google` (version 8.8.x). A **resource** is one thing Terraform manages. The **state** is a file in which Terraform remembers what it created. This repository was built with Terraform 1.17.0 and requires 1.9 or newer.

## 2. Why this repository uses it

A landing zone is the part of the cloud that must be built the same way every time: folders, projects, policies, a shared network, a perimeter. As code, those pieces can be reviewed, tested without a cloud account, applied in dry-run mode first, and removed with one command. One more reason is specific to this repository: Terraform reads the same YAML files the Python tool checks, so the build and the checks share one source of truth.

## 3. Where it appears

| Path | What it does |
| --- | --- |
| `infra/modules/*/` | Seven reusable pieces (`folders`, `project`, `org-policies`, `lab-identities`, `shared-vpc`, `sensitive-bucket`, `perimeter`), each with `main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`, a README and tests. |
| `infra/environments/lab/` | The composition: reads the YAML files, calls the modules and wires them together. |
| `infra/environments/lab/lab.tfvars.example` | Example values for the offline plan. |
| `infra/environments/lab/.terraform.lock.hcl` | Pins the exact provider version and checksums. |
| `infra/environments/lab/backend.tf.example` | How to keep state in a bucket (not used by default). |
| `scripts/deploy.sh`, `enforce.sh`, `teardown.sh` | Run `terraform init`, `apply` and `destroy`. |

## 4. How it works underneath

1. `terraform init` downloads the provider into a hidden `.terraform/` folder and records its version and hashes in `.terraform.lock.hcl`. With `-backend=false` it does not set up remote state, so it needs no credentials.
2. `terraform validate` checks that the files are well formed and the arguments exist, without contacting any cloud.
3. `terraform plan` reads the files and the **state**, asks the provider what exists, and prints what it would change: `+` create, `~` change, `-` destroy. Nothing in this configuration reads from Google Cloud while planning, so it plans offline; the provider still needs *a* token to start, so `make plan` sets a placeholder `GOOGLE_OAUTH_ACCESS_TOKEN`.
4. `terraform apply` performs the plan and writes the new state. `terraform destroy` removes everything in the state.

Terraform builds a **dependency graph**: if resource B uses `A.id`, B waits for A. When two things are related without a visible reference, you add `depends_on`. Values that are only known after creation are shown as `(known after apply)`.

A **module** is a folder of Terraform files used as a function: variables in, outputs out. The environment calls modules with `module "name" { source = "..." }`. `for_each` creates one copy of a resource or module per item of a map or set; `count` creates a number of copies. Both can make a resource optional (`count = 0`).

## 5. Walkthrough of this repository's use

### Version pins and the provider

`infra/environments/lab/versions.tf`

```hcl
terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.8"
    }
  }

  # Local state is enough for a lab. A real landing zone keeps its state in a locked bucket (see backend.tf.example).
}

provider "google" {
  # Organization policies and Access Context Manager are charged to a quota project, which must already exist
  # and have those APIs enabled: scripts/bootstrap.sh creates it.
  user_project_override = true
  billing_project       = var.quota_project_id
}
```

`required_version` refuses an older Terraform. `required_providers` names the provider, its registry address and the allowed versions: `~> 8.8` means 8.8 or newer but below 9.0. The modules use the wider window `>= 8.0, < 9.0`; the environment's lock file decides the exact version (`8.8.1`). In the `provider "google"` block, `user_project_override = true` and `billing_project` make the organization-level calls (policies, Access Context Manager) count against the bootstrap project, because those APIs need a project to bill and quota.

### Variables with checks

`infra/environments/lab/variables.tf`

```hcl
variable "org_id" {
  description = "Organization id (gcloud organizations list). A free Cloud Identity domain gives you one."
  type        = string

  validation {
    condition     = can(regex("^[0-9]+$", var.org_id))
    error_message = "org_id must contain digits only."
  }
}
```

A `variable` is an input. The `validation` block runs when the plan is made: `can(regex("^[0-9]+$", var.org_id))` is true only if the text is digits. A domain name in this place stops the plan with your message.

`infra/environments/lab/variables.tf`

```hcl
variable "policy_mode" {
  description = "dry_run writes only the policies' dry-run spec (violations are logged, nothing is blocked); enforced also enforces them."
  type        = string
  default     = "dry_run"

  validation {
    condition     = contains(["dry_run", "enforced"], var.policy_mode)
    error_message = "policy_mode must be dry_run or enforced."
  }
}
```

`default = "dry_run"` is the safe starting point: the tool never enforces by accident. `contains([...], var.policy_mode)` limits the value to two words. `perimeter_mode` is the same.

### The YAML files become data

`infra/environments/lab/main.tf`

```hcl
locals {
  # The design and the policies are data. The same files are checked and simulated by the landing-zone tool.
  design      = yamldecode(file("${path.module}/../../../design/landing-zone.yaml"))
  policy_file = yamldecode(file("${path.module}/../../../policies/org-policies.yaml"))

  organization = "organizations/${var.org_id}"
  region       = local.design.shared_vpc.region
  host_name    = local.design.shared_vpc.host_project

  projects    = { for p in local.design.projects : p.name => p }
  project_ids = { for name, _ in local.projects : name => "${name}-${var.name_suffix}" }
  subnets     = { for s in local.design.shared_vpc.subnets : s.name => s }
  bucket_name = "${local.design.sensitive_data.bucket}-${var.name_suffix}"

  # APIs per project role. The perimeter restricts Cloud Storage in the data project, so that one needs it.
  services = {
    data    = ["iam.googleapis.com", "logging.googleapis.com", "storage.googleapis.com"]
    service = ["compute.googleapis.com", "iam.googleapis.com", "logging.googleapis.com"]
    host    = ["compute.googleapis.com", "logging.googleapis.com"]
  }

  policies = [
    for p in local.policy_file.policies : {
      constraint     = p.constraint
      kind           = p.kind
      enforce        = try(p.enforce, false)
      allowed_values = try(p.allowed_values, [])
      deny_all       = try(p.deny_all, false)
      folder         = startswith(try(p.level, "organization"), "folder:") ? trimprefix(p.level, "folder:") : null
    }
  ]

  access_levels = {
    for level in local.design.access_levels : level.name => coalesce(var.office_ip_subnetworks, level.ip_subnetworks)
  }

  # The test identity that stands in for each team, by service project.
  testers = {
    "prod-app" = module.lab_identities.team_prod_member
    "dev-app"  = module.lab_identities.team_dev_member
  }
}
```

- `locals` are named values computed once.
- `yamldecode(file("${path.module}/../../../design/landing-zone.yaml"))` reads the design file and turns it into Terraform values. `path.module` is the folder of this file, so the path works from any directory.
- `"organizations/${var.org_id}"` substitutes a value inside a string.
- `{ for p in local.design.projects : p.name => p }` is a **for expression**: it builds a map (name to project) from a list. `project_ids` builds each project id by adding the suffix, because project ids and bucket names are global.
- `[ for p in ... : { ... } ]` builds a list of objects; `try(p.enforce, false)` returns the value or the fallback when the key is absent; `startswith(...) ? trimprefix(...) : null` is a conditional (`condition ? a : b`).
- `coalesce(var.office_ip_subnetworks, level.ip_subnetworks)` returns the first value that is not null: the variable if set, else the design file's range.

### Composition

`infra/environments/lab/main.tf`

```hcl
module "projects" {
  source   = "../../modules/project"
  for_each = local.projects

  name            = each.key
  project_id      = local.project_ids[each.key]
  folder_id       = module.folders.ids[each.value.folder]
  billing_account = var.billing_account
  services        = local.services[each.value.role]
  labels          = var.labels
}
```

`for_each = local.projects` creates the module once per project. `each.key` is the project name and `each.value` its entry. `module.folders.ids[each.value.folder]` reads another module's output; that reference makes Terraform create the folders first.

`infra/environments/lab/main.tf`

```hcl
module "shared_vpc" {
  source = "../../modules/shared-vpc"

  host_project_id = module.projects[local.host_name].project_id
  service_projects = {
    for s in local.design.shared_vpc.subnets : s.service_project => module.projects[s.service_project].project_id
  }
  network_name = local.design.shared_vpc.network
  region       = local.region
  subnets = {
    for name, s in local.subnets : name => {
      cidr  = s.cidr
      users = concat(s.user_groups, [local.testers[s.service_project]])
    }
  }
}
```

The arguments are built from the design with more `for` expressions; `concat(a, b)` joins two lists, adding the test identity to the groups that may use each subnet.

`infra/environments/lab/main.tf`

```hcl
module "perimeter" {
  source = "../../modules/perimeter"

  organization        = local.organization
  access_policy_id    = var.access_policy_id
  name                = local.design.perimeter.name
  title               = local.design.perimeter.title
  project_numbers     = [for name in local.design.perimeter.projects : module.projects[name].number]
  restricted_services = local.design.perimeter.restricted_services
  access_levels       = local.access_levels
  access_level_names  = local.design.perimeter.access_levels
  mode                = var.perimeter_mode
}
```

Nothing here says "dry run" or "enforced" in code: `mode = var.perimeter_mode`, so enforcing is a variable change.

### Optional resources, dynamic blocks and the two specs

`infra/modules/org-policies/main.tf`

```hcl
locals {
  # One policy per constraint per level: the key is the constraint plus where it is set.
  policies = { for p in var.policies : "${p.constraint}@${coalesce(p.folder, "organization")}" => p }

  parents = {
    for key, p in local.policies : key => p.folder == null ? var.organization : var.folder_parents[p.folder]
  }

  # The rule each policy carries, as the three optional fields of the provider's rules block.
  rules = {
    for key, p in local.policies : key => {
      enforce        = p.kind == "boolean" ? (p.enforce ? "TRUE" : "FALSE") : null
      deny_all       = p.kind == "list" && p.deny_all ? "TRUE" : null
      allowed_values = p.kind == "list" ? p.allowed_values : []
    }
  }
}
```

The key of each policy is the constraint plus where it is set (`gcp.resourceLocations@organization`), so a constraint can be set once at the organization and again on a folder. `p.kind == "boolean" ? (p.enforce ? "TRUE" : "FALSE") : null` translates the file's `true` into the provider's text `"TRUE"`, and leaves the field out (`null`) for list policies.

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

- `dry_run_spec` is always written: the policy is audit-only until you enforce.
- `dynamic "spec"` writes the enforced `spec` block only when `var.mode == "enforced"`: its `for_each` is a list of one item (`[1]`) or an empty list, which switches the block on or off.
- The nested `dynamic "values"` writes the allowed-values block only when the list is not empty.

`infra/modules/perimeter/main.tf`

```hcl
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

The provider describes `use_explicit_dry_run_spec` this way: normally a dry-run spec implicitly exists and equals the enforced `status`; setting the flag lets you give a different `spec` that is only tested. Here `spec` always exists (dry run) and `status` (enforced) appears only in enforced mode. `depends_on` makes the perimeter wait for the access level, which is referenced only by name.

`infra/modules/perimeter/main.tf`

```hcl
resource "google_access_context_manager_access_policy" "this" {
  count = var.access_policy_id == "" ? 1 : 0

  parent = var.organization
  title  = "${var.name} access policy"
}
```

`count = var.access_policy_id == "" ? 1 : 0` creates the access policy only when none was given (an organization can have only one). `local.access_policy_id` then picks the given id or `google_access_context_manager_access_policy.this[0].name`.

### A map keyed by fixed labels

`infra/modules/shared-vpc/main.tf`

```hcl
locals {
  # Key: subnet plus position, so the keys are known at plan time even when a member is not.
  subnet_users = merge([
    for subnet, config in var.subnets : {
      for index, member in config.users : "${subnet}/${index}" => { subnet = subnet, member = member }
    }
  ]...)
}
```

`for_each` keys must be known when the plan is made. Members can be unknown until apply, so the key is the subnet name plus the position (`subnet-prod/0`). `merge([ ... ]...)` merges a list of maps into one; the three dots expand the list into separate arguments.

### Outputs

`infra/environments/lab/outputs.tf`

```hcl
output "perimeter" {
  description = "Perimeter resource name and mode."
  value = {
    name = module.perimeter.perimeter_name
    mode = module.perimeter.mode
  }
}
```

Outputs print after `apply` and are what the tests assert on.

## Every Terraform file, module by module

The earlier sections explained the language by examples. This part covers every file of `infra/`, so that nothing is left out. First the vocabulary that every file uses.

- A **file** ending in `.tf` is read by Terraform together with all other `.tf` files in the same folder, as one configuration. The names `main.tf`, `variables.tf`, `outputs.tf` and `versions.tf` are only a convention for what goes where.
- A **block** is `type "label" "label" { ... }`. `resource "google_folder" "this" { ... }` declares a thing to manage; `google_folder` is its type, `this` is a name you choose to refer to it (`google_folder.this`). `variable`, `output`, `locals`, `module`, `data` and `terraform` are other block types.
- An **argument** is `name = value` inside a block. Values can be text in double quotes, numbers, `true`/`false`, lists `[...]`, and maps/objects `{ key = value }`.
- A **type** says what a variable may hold: `string`, `bool`, `number`, `list(string)` (a list of texts), `map(string)` (named texts), `object({ ... })` (a fixed set of named fields of given types), and `optional(type, default)` inside an object (a field that may be left out).
- An **expression** computes a value: `var.x` reads a variable, `local.x` a local, `module.m.out` a module's output, `resource_type.name.attribute` a resource's attribute. Functions are called like `length(list)`.
- `# ...` starts a comment.

The seven modules all have the same `versions.tf`:

`infra/modules/folders/versions.tf`

```hcl
terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 8.0, < 9.0"
    }
  }
}
```

- `required_version = ">= 1.9"`: Terraform itself must be at least 1.9.
- `required_providers` says which plug-in provides the resources: `source = "hashicorp/google"` is its address in the public registry; `version = ">= 8.0, < 9.0"` allows any 8.x release. A module declares a window, and the environment's `~> 8.8` and lock file choose the exact version.

### Module `folders`

`infra/modules/folders/variables.tf`

```hcl
variable "parent" {
  description = "Parent of every folder: organizations/ID or folders/ID."
  type        = string

  validation {
    condition     = can(regex("^(organizations|folders)/[0-9]+$", var.parent))
    error_message = "parent must look like organizations/123456789012 or folders/123456789012."
  }
}

variable "names" {
  description = "Display names of the folders to create."
  type        = list(string)

  validation {
    condition     = length(var.names) == length(distinct(var.names))
    error_message = "Folder names must be unique."
  }
}

variable "deletion_protection" {
  description = "Refuse to delete the folders. False for a lab so the teardown works."
  type        = bool
  default     = false
}
```

- `parent`: required (no default). The check `can(regex("^(organizations|folders)/[0-9]+$", var.parent))` is true for `organizations/123456789012` or `folders/123`. `can(expression)` returns false instead of failing when the expression fails; `regex` fails when it does not match.
- `names`: a list of texts. `length(var.names) == length(distinct(var.names))` compares the list's length with the length after removing duplicates; equal means no duplicates.
- `deletion_protection`: a boolean with the default `false`, so the lab can be torn down.

`infra/modules/folders/outputs.tf`

```hcl
output "ids" {
  description = "Folder name => folder id (the number only)."
  value       = { for name, folder in google_folder.this : name => folder.folder_id }
}

output "names" {
  description = "Folder name => resource name (folders/ID), the form parents take."
  value       = { for name, folder in google_folder.this : name => folder.name }
}
```

- An `output` publishes a value from the module. `{ for name, folder in google_folder.this : name => folder.folder_id }` builds a map from the folder name to the folder's number. `google_folder.this` is a map of resources because the resource used `for_each`; `folder.folder_id` is the number, `folder.name` the full name `folders/ID` (the form a child's `parent` takes).

The resource itself (`main.tf`) was walked through in `resource-hierarchy.md`. The tests are described in `terraform-test.md`.

### Module `project`

`infra/modules/project/variables.tf`

```hcl
variable "name" {
  description = "Display name, also the lesson's project name."
  type        = string
}

variable "project_id" {
  description = "Globally unique project id (6-30 characters)."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be 6-30 characters: lowercase letters, digits and hyphens, starting with a letter."
  }
}

variable "folder_id" {
  description = "Folder the project lives in (the number only)."
  type        = string
}

variable "billing_account" {
  description = "Billing account id."
  type        = string
}

variable "services" {
  description = "APIs to enable."
  type        = list(string)
  default     = []
}

variable "audit_all_services" {
  description = "Turn on admin-read, data-read and data-write audit logs for every service in the project."
  type        = bool
  default     = true
}

variable "labels" {
  description = "Labels for the project."
  type        = map(string)
  default     = {}
}

variable "deletion_policy" {
  description = "PREVENT, ABANDON or DELETE. DELETE in a lab so terraform destroy schedules the project for deletion."
  type        = string
  default     = "DELETE"

  validation {
    condition     = contains(["PREVENT", "ABANDON", "DELETE"], var.deletion_policy)
    error_message = "deletion_policy must be PREVENT, ABANDON or DELETE."
  }
}
```

- `name` and `project_id`: the display name and the global id. The id check is the same pattern the Google rules use: a lowercase letter, then 4 to 28 letters, digits or hyphens, ending in a letter or digit (6 to 30 characters).
- `folder_id`, `billing_account`: required texts.
- `services`: the APIs to enable, default the empty list.
- `audit_all_services`: a boolean, default `true`, that switches the audit configuration on (the resource uses it as `count`).
- `labels`: a map of texts (default empty). A **label** is a key and value stuck onto a resource for grouping and cost reports.
- `deletion_policy`: default `"DELETE"`; the check `contains(["PREVENT", "ABANDON", "DELETE"], var.deletion_policy)` limits the value to those three words.

`infra/modules/project/outputs.tf`

```hcl
output "project_id" {
  description = "Project id."
  value       = google_project.this.project_id
}

output "number" {
  description = "Project number."
  value       = google_project.this.number
}
```

The id and the **number**. The number is what the perimeter needs (`projects/NUMBER`).

### Module `org-policies`

`infra/modules/org-policies/variables.tf`

```hcl
variable "organization" {
  description = "organizations/ID, the parent of organization-level policies."
  type        = string

  validation {
    condition     = can(regex("^organizations/[0-9]+$", var.organization))
    error_message = "organization must look like organizations/123456789012."
  }
}

variable "folder_parents" {
  description = "Folder name => folders/ID, for policies set at folder level."
  type        = map(string)
  default     = {}
}

variable "mode" {
  description = "dry_run writes only the dry-run spec (violations are logged, nothing is blocked); enforced also writes the real spec."
  type        = string
  default     = "dry_run"

  validation {
    condition     = contains(["dry_run", "enforced"], var.mode)
    error_message = "mode must be dry_run or enforced."
  }
}

variable "policies" {
  description = "The policy entries of policies/org-policies.yaml."
  type = list(object({
    constraint     = string
    kind           = string
    enforce        = optional(bool, false)
    allowed_values = optional(list(string), [])
    deny_all       = optional(bool, false)
    folder         = optional(string)
  }))

  validation {
    condition     = alltrue([for p in var.policies : contains(["boolean", "list"], p.kind)])
    error_message = "kind must be boolean or list."
  }

  validation {
    condition     = alltrue([for p in var.policies : p.kind == "boolean" || (length(p.allowed_values) > 0) != p.deny_all])
    error_message = "A list policy needs exactly one of allowed_values and deny_all."
  }
}
```

- `organization` must look like `organizations/123456789012`. `folder_parents` maps a folder name to its `folders/ID`; default is the empty map.
- `mode` limits to `dry_run` or `enforced` and defaults to `dry_run`.
- `policies` is a list of objects. Fields without `optional` (`constraint`, `kind`) are required in each entry; `enforce = optional(bool, false)`, `allowed_values = optional(list(string), [])`, `deny_all = optional(bool, false)` default as written; `folder = optional(string)` defaults to `null` (no folder: the organization).
- The first validation: `alltrue([for p in var.policies : contains(["boolean", "list"], p.kind)])`. A `for` expression in `[ ]` builds a list of true/false values, one per policy; `alltrue` is true only if every one is true.
- The second validation: `p.kind == "boolean" || (length(p.allowed_values) > 0) != p.deny_all`. For a boolean policy it is always true; for a list policy exactly one of "has allowed values" and "deny all" must be true (`!=` between two booleans is "exclusive or").

`infra/modules/org-policies/outputs.tf`

```hcl
output "constraints" {
  description = "Constraint@level of every policy managed here."
  value       = sort(keys(local.policies))
}

output "mode" {
  description = "dry_run or enforced."
  value       = var.mode
}
```

`keys(local.policies)` is the list of map keys (`constraint@level`), and `sort` orders them alphabetically so the output is stable. The second output echoes the mode.

### Module `lab-identities`

`infra/modules/lab-identities/variables.tf`

```hcl
variable "prod_app_project_id" {
  description = "Project id of prod-app."
  type        = string
}

variable "dev_app_project_id" {
  description = "Project id of dev-app."
  type        = string
}

variable "data_project_id" {
  description = "Project id of prod-data."
  type        = string
}

variable "operator_member" {
  description = "Who may impersonate the test identities, for example user:you@example-lab.org."
  type        = string

  validation {
    condition     = can(regex("^(user|group|serviceAccount):", var.operator_member))
    error_message = "operator_member must start with user:, group: or serviceAccount:."
  }
}
```

Three project ids (where each identity lives) and the operator. `^(user|group|serviceAccount):` demands a valid member prefix, because IAM members are written `user:EMAIL`, `group:EMAIL` or `serviceAccount:EMAIL`.

`infra/modules/lab-identities/outputs.tf`

```hcl
output "team_prod_member" {
  description = "IAM member of the team-prod test identity."
  value       = "serviceAccount:${google_service_account.team_prod.email}"
}

output "team_dev_member" {
  description = "IAM member of the team-dev test identity."
  value       = "serviceAccount:${google_service_account.team_dev.email}"
}

output "data_reader_member" {
  description = "IAM member of the data reader."
  value       = "serviceAccount:${google_service_account.data_reader.email}"
}

output "emails" {
  description = "Emails of the three test identities."
  value = {
    team_prod   = google_service_account.team_prod.email
    team_dev    = google_service_account.team_dev.email
    data_reader = google_service_account.data_reader.email
  }
}
```

- The three `*_member` outputs build the IAM member text: `"serviceAccount:${google_service_account.team_prod.email}"` inserts the account's generated email into a string. The environment passes them to the shared-VPC module and the bucket.
- `emails` is a map of the three emails for the proofs and for humans.

### Module `shared-vpc`

`infra/modules/shared-vpc/variables.tf`

```hcl
variable "host_project_id" {
  description = "Id of the host project that owns the network."
  type        = string
}

variable "service_projects" {
  description = "Service projects attached to the host, keyed by a fixed label (the project name)."
  type        = map(string)
}

variable "network_name" {
  description = "Name of the shared VPC network."
  type        = string
}

variable "region" {
  description = "Region of every subnet."
  type        = string
}

variable "subnets" {
  description = "Subnets by name: the CIDR range and the IAM members that may use the subnet (roles/compute.networkUser)."
  type = map(object({
    cidr  = string
    users = list(string)
  }))

  validation {
    condition     = alltrue([for s in values(var.subnets) : can(cidrhost(s.cidr, 0))])
    error_message = "Every subnet needs a valid CIDR range."
  }

  validation {
    condition     = alltrue([for s in values(var.subnets) : length(s.users) > 0])
    error_message = "A subnet nobody may use is a mistake: give it at least one user."
  }
}
```

- `host_project_id`, `network_name` and `region` are plain texts.
- `service_projects` is a map of texts keyed by the project's design name (a fixed label, so the keys are known at plan time).
- `subnets` is a map of objects with a `cidr` and a list of `users`. Validation one: `can(cidrhost(s.cidr, 0))` is true when the text is a valid range (`cidrhost` computes the address number 0 of a range and fails on bad text). Validation two: every subnet has at least one user. `values(var.subnets)` is the list of the map's values.

`infra/modules/shared-vpc/outputs.tf`

```hcl
output "network" {
  description = "Self link of the shared network."
  value       = google_compute_network.this.self_link
}

output "subnets" {
  description = "Subnet name => self link."
  value       = { for name, subnet in google_compute_subnetwork.this : name => subnet.self_link }
}

output "subnet_cidrs" {
  description = "Subnet name => CIDR range."
  value       = { for name, subnet in var.subnets : name => subnet.cidr }
}
```

`self_link` is the full URL Google gives a resource; `subnet_cidrs` reads the variable back, which is what the environment tests compare.

### Module `sensitive-bucket`

`infra/modules/sensitive-bucket/variables.tf`

```hcl
variable "project_id" {
  description = "Project that owns the bucket."
  type        = string
}

variable "name" {
  description = "Globally unique bucket name."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$", var.name))
    error_message = "name must be 3-63 characters: lowercase letters, digits, dot, underscore and hyphen."
  }
}

variable "location" {
  description = "Bucket location; the organization policy only allows EU locations."
  type        = string
}

variable "viewer_members" {
  description = "Members that may read objects in this bucket, keyed by a fixed label."
  type        = map(string)
  default     = {}
}

variable "force_destroy" {
  description = "Delete the bucket even when it holds objects. True only for a lab."
  type        = bool
  default     = false
}

variable "labels" {
  description = "Labels for the bucket."
  type        = map(string)
  default     = {}
}
```

The name check `^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$` is Google's bucket-name rule (3 to 63 characters; lowercase letters, digits, dot, underscore, hyphen; start and end with a letter or digit). `viewer_members` is a map from a fixed label to a member text (default empty).

`infra/modules/sensitive-bucket/outputs.tf`

```hcl
output "name" {
  description = "Bucket name."
  value       = google_storage_bucket.this.name
}

output "viewer_members" {
  description = "Members granted objectViewer."
  value       = sort(values(var.viewer_members))
}
```

`sort(values(var.viewer_members))` is the sorted list of members.

### Module `perimeter`

`infra/modules/perimeter/variables.tf`

```hcl
variable "organization" {
  description = "organizations/ID, the parent of the access policy."
  type        = string

  validation {
    condition     = can(regex("^organizations/[0-9]+$", var.organization))
    error_message = "organization must look like organizations/123456789012."
  }
}

variable "access_policy_id" {
  description = "Id (the number) of the organization's existing access policy. Empty creates one."
  type        = string
  default     = ""
}

variable "name" {
  description = "Perimeter name: letters, digits and underscores."
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_]{0,49}$", var.name))
    error_message = "name must start with a letter and contain letters, digits and underscores only."
  }
}

variable "title" {
  description = "Human-readable title."
  type        = string
}

variable "project_numbers" {
  description = "Numbers of the projects inside the perimeter."
  type        = list(string)

  validation {
    condition     = length(var.project_numbers) > 0
    error_message = "A perimeter around no project protects nothing."
  }
}

variable "restricted_services" {
  description = "Services the perimeter restricts, for example storage.googleapis.com."
  type        = list(string)

  validation {
    condition     = length(var.restricted_services) > 0
    error_message = "Restrict at least one service."
  }
}

variable "access_levels" {
  description = "Access level name => IP ranges whose callers count as trusted."
  type        = map(list(string))
  default     = {}
}

variable "access_level_names" {
  description = "Names of the access levels the perimeter accepts (a subset of access_levels)."
  type        = list(string)
  default     = []
}

variable "mode" {
  description = "dry_run logs what the perimeter would block; enforced blocks it. Always run dry_run first."
  type        = string
  default     = "dry_run"

  validation {
    condition     = contains(["dry_run", "enforced"], var.mode)
    error_message = "mode must be dry_run or enforced."
  }
}
```

- Names must match Google's formats: `organizations/ID`, and a perimeter name that starts with a letter and holds letters, digits and underscores (up to 50).
- `project_numbers` and `restricted_services` must not be empty, because a perimeter around nothing, or restricting nothing, protects nothing.
- `access_levels` is a map from a name to the list of ranges (`map(list(string))`); `access_level_names` lists those the perimeter accepts.
- `mode` as in the policies module.

`infra/modules/perimeter/outputs.tf`

```hcl
output "access_policy_id" {
  description = "Id of the access policy the perimeter belongs to."
  value       = local.access_policy_id
}

output "perimeter_name" {
  description = "Full resource name of the perimeter."
  value       = google_access_context_manager_service_perimeter.this.name
}

output "mode" {
  description = "dry_run or enforced."
  value       = var.mode
}
```

The policy id (given or created), the perimeter's full name and the mode.

### The `lab` environment

`infra/environments/lab/main.tf`

```hcl
locals {
  # The design and the policies are data. The same files are checked and simulated by the landing-zone tool.
  design      = yamldecode(file("${path.module}/../../../design/landing-zone.yaml"))
  policy_file = yamldecode(file("${path.module}/../../../policies/org-policies.yaml"))

  organization = "organizations/${var.org_id}"
  region       = local.design.shared_vpc.region
  host_name    = local.design.shared_vpc.host_project

  projects    = { for p in local.design.projects : p.name => p }
  project_ids = { for name, _ in local.projects : name => "${name}-${var.name_suffix}" }
  subnets     = { for s in local.design.shared_vpc.subnets : s.name => s }
  bucket_name = "${local.design.sensitive_data.bucket}-${var.name_suffix}"

  # APIs per project role. The perimeter restricts Cloud Storage in the data project, so that one needs it.
  services = {
    data    = ["iam.googleapis.com", "logging.googleapis.com", "storage.googleapis.com"]
    service = ["compute.googleapis.com", "iam.googleapis.com", "logging.googleapis.com"]
    host    = ["compute.googleapis.com", "logging.googleapis.com"]
  }

  policies = [
    for p in local.policy_file.policies : {
      constraint     = p.constraint
      kind           = p.kind
      enforce        = try(p.enforce, false)
      allowed_values = try(p.allowed_values, [])
      deny_all       = try(p.deny_all, false)
      folder         = startswith(try(p.level, "organization"), "folder:") ? trimprefix(p.level, "folder:") : null
    }
  ]

  access_levels = {
    for level in local.design.access_levels : level.name => coalesce(var.office_ip_subnetworks, level.ip_subnetworks)
  }

  # The test identity that stands in for each team, by service project.
  testers = {
    "prod-app" = module.lab_identities.team_prod_member
    "dev-app"  = module.lab_identities.team_dev_member
  }
}

module "folders" {
  source = "../../modules/folders"

  parent = local.organization
  names  = [for f in local.design.folders : f.name]
}

module "projects" {
  source   = "../../modules/project"
  for_each = local.projects

  name            = each.key
  project_id      = local.project_ids[each.key]
  folder_id       = module.folders.ids[each.value.folder]
  billing_account = var.billing_account
  services        = local.services[each.value.role]
  labels          = var.labels
}

# Step 2. Set once, at the top. Written in dry-run mode first: violations are logged and nothing is blocked.
module "org_policies" {
  source = "../../modules/org-policies"

  organization   = local.organization
  folder_parents = module.folders.names
  mode           = var.policy_mode
  policies       = local.policies
}

module "lab_identities" {
  source = "../../modules/lab-identities"

  prod_app_project_id = module.projects["prod-app"].project_id
  dev_app_project_id  = module.projects["dev-app"].project_id
  data_project_id     = module.projects["prod-data"].project_id
  operator_member     = var.operator_member
}

# Step 3. A host project with a shared VPC; each team may use only its own subnet.
module "shared_vpc" {
  source = "../../modules/shared-vpc"

  host_project_id = module.projects[local.host_name].project_id
  service_projects = {
    for s in local.design.shared_vpc.subnets : s.service_project => module.projects[s.service_project].project_id
  }
  network_name = local.design.shared_vpc.network
  region       = local.region
  subnets = {
    for name, s in local.subnets : name => {
      cidr  = s.cidr
      users = concat(s.user_groups, [local.testers[s.service_project]])
    }
  }
}

module "sensitive_bucket" {
  source = "../../modules/sensitive-bucket"

  project_id     = module.projects[local.design.sensitive_data.project].project_id
  name           = local.bucket_name
  location       = local.region
  labels         = var.labels
  force_destroy  = true
  viewer_members = { data_reader = module.lab_identities.data_reader_member }
}

# Steps 4 and 5. The perimeter surrounds the data project only. Dry run first; enforce when the logs are clean.
module "perimeter" {
  source = "../../modules/perimeter"

  organization        = local.organization
  access_policy_id    = var.access_policy_id
  name                = local.design.perimeter.name
  title               = local.design.perimeter.title
  project_numbers     = [for name in local.design.perimeter.projects : module.projects[name].number]
  restricted_services = local.design.perimeter.restricted_services
  access_levels       = local.access_levels
  access_level_names  = local.design.perimeter.access_levels
  mode                = var.perimeter_mode
}
```

The first 42 lines (`locals`) and each `module` block were explained above. The ordering in the file is the order of the lesson: folders and projects, then the policies and the identities, then the shared network, the bucket and the perimeter. Terraform ignores the order in the file and orders by references.

`infra/environments/lab/variables.tf`

```hcl
variable "org_id" {
  description = "Organization id (gcloud organizations list). A free Cloud Identity domain gives you one."
  type        = string

  validation {
    condition     = can(regex("^[0-9]+$", var.org_id))
    error_message = "org_id must contain digits only."
  }
}

variable "billing_account" {
  description = "Billing account id (gcloud billing accounts list)."
  type        = string
}

variable "quota_project_id" {
  description = "An existing project that is charged for the organization-level API calls (scripts/bootstrap.sh creates it)."
  type        = string
}

variable "name_suffix" {
  description = "Appended to project ids and the bucket name, which are global: 3 to 6 lowercase letters or digits."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{3,6}$", var.name_suffix))
    error_message = "name_suffix must be 3 to 6 lowercase letters or digits."
  }
}

variable "operator_member" {
  description = "Who runs the proofs and may impersonate the test identities, for example user:you@example-lab.org."
  type        = string
}

variable "policy_mode" {
  description = "dry_run writes only the policies' dry-run spec (violations are logged, nothing is blocked); enforced also enforces them."
  type        = string
  default     = "dry_run"

  validation {
    condition     = contains(["dry_run", "enforced"], var.policy_mode)
    error_message = "policy_mode must be dry_run or enforced."
  }
}

variable "perimeter_mode" {
  description = "dry_run logs what the perimeter would block; enforced blocks it. Always run dry_run first."
  type        = string
  default     = "dry_run"

  validation {
    condition     = contains(["dry_run", "enforced"], var.perimeter_mode)
    error_message = "perimeter_mode must be dry_run or enforced."
  }
}

variable "access_policy_id" {
  description = "Id (the number) of the organization's existing access policy. Empty creates one; an organization can have only one."
  type        = string
  default     = ""
}

variable "office_ip_subnetworks" {
  description = "Address ranges of the 'office' access level. Null keeps the design file's documentation range, which matches nobody, so a laptop is outside the access level (step 5's second attack)."
  type        = list(string)
  default     = null
}

variable "labels" {
  description = "Labels applied to every project and bucket."
  type        = map(string)
  default = {
    environment = "lab"
    project     = "landing-zone-slice"
    managed-by  = "terraform"
  }
}
```

- `org_id`, `name_suffix`, `policy_mode` and `perimeter_mode` were explained above.
- `billing_account`, `quota_project_id`, `operator_member`: required texts. `access_policy_id` defaults to `""` (create one). `office_ip_subnetworks` is `list(string)` with default `null`: null means "not given", so `coalesce` takes the design file's range.
- `labels` is a map with a default of three labels applied to every project and the bucket.

`infra/environments/lab/outputs.tf`

```hcl
output "project_ids" {
  description = "Design name => project id."
  value       = local.project_ids
}

output "project_numbers" {
  description = "Design name => project number."
  value       = { for name, project in module.projects : name => project.number }
}

output "folders" {
  description = "Folder name => folders/ID."
  value       = module.folders.names
}

output "policy_constraints" {
  description = "Constraint@level of every organization policy."
  value       = module.org_policies.constraints
}

output "policy_mode" {
  description = "dry_run or enforced."
  value       = module.org_policies.mode
}

output "subnet_cidrs" {
  description = "Shared VPC subnet => CIDR range."
  value       = module.shared_vpc.subnet_cidrs
}

output "perimeter" {
  description = "Perimeter resource name and mode."
  value = {
    name = module.perimeter.perimeter_name
    mode = module.perimeter.mode
  }
}

output "access_policy_id" {
  description = "Access policy the perimeter belongs to."
  value       = module.perimeter.access_policy_id
}

output "sensitive_bucket" {
  description = "The bucket that holds customers.csv."
  value       = module.sensitive_bucket.name
}

output "test_identities" {
  description = "Emails of the identities the proofs impersonate."
  value       = module.lab_identities.emails
}
```

Each `output` is shown after `terraform apply` and is what the environment test reads. `{ for name, project in module.projects : name => project.number }` loops over a module that used `for_each`. `output "perimeter"` returns an object with two fields.

`infra/environments/lab/lab.tfvars.example`

```hcl
# Copy to lab.tfvars and edit. The values below are placeholders; `make plan` uses this file as it is.
org_id           = "123456789012"
billing_account  = "AAAAAA-BBBBBB-CCCCCC"
quota_project_id = "lz-bootstrap-ab12cd"
name_suffix      = "ab12cd"
operator_member  = "user:operator@example-lab.org"

# Both start in dry-run mode. scripts/enforce.sh flips them after you have read the logs.
policy_mode    = "dry_run"
perimeter_mode = "dry_run"

# Leave empty to create the organization's access policy; set to its number if one already exists.
access_policy_id = ""

# Null keeps the design file's documentation range (203.0.113.0/24), which matches nobody. Your laptop is then outside
# the access level, which is what step 5's second attack needs.
# office_ip_subnetworks = ["198.51.100.7/32"]
```

A **`.tfvars` file** gives values to variables (`name = value` lines). This one is an example: copy it to `lab.tfvars` and edit; real `.tfvars` files are ignored by Git. `make plan` uses the example as it is, so it holds placeholder values (`123456789012`, `AAAAAA-BBBBBB-CCCCCC`). The commented last line shows how to put your own address in.

`infra/environments/lab/backend.tf.example`

```hcl
# Copy to backend.tf for remote state. The bucket is created by hand, with versioning, before `terraform init`.
terraform {
  backend "gcs" {
    bucket = "EXAMPLE-terraform-state"
    prefix = "gcp-landing-zone-slice/lab"
  }
}
```

A **backend** says where the state file lives. By default it is a local file. `backend "gcs"` keeps it in a Cloud Storage bucket (`bucket`, plus a `prefix` that names the folder inside). The file ends in `.example` so Terraform ignores it; copy it to `backend.tf` to use it.

### The lock file

`infra/environments/lab/.terraform.lock.hcl`

```hcl
# This file is maintained automatically by "terraform init".
# Manual edits may be lost in future updates.

provider "registry.terraform.io/hashicorp/google" {
  version     = "8.8.1"
  constraints = ">= 8.0.0, ~> 8.8, < 9.0.0"
  hashes = [
    "h1:cj2w8+P7qqGDbhG+PIJcXmtu0CMBNLqdTNLpLgvhJrw=",
    "zh:1510c0a5ec95676bf9df8f4c4798eb21f1ddb49f1d0bfc52e323fcdec5240bad",
    "zh:18122322d83564567bfa8c4075f1b33263bf30217345c4cf967e5d9fb7df6134",
    "zh:3468de1e43ad4bee6d5191c23be7dbb39f6c1559027c598f99869f7e7fe180ba",
    "zh:55bfd12669b8dd9913e5ee00df060c3f53c2976a92291262c02eaa0504e6b5d4",
    "zh:5b643a92495934a22c594aca095eace27c817d83ef896042e4360b87216285df",
    "zh:5e9326c8392700c2d8a998b19ff253b7fcbe01a39e14c5518233da1b98d4d99b",
    "zh:9522b2ed7cd335488c7a91509bb70cf134a318b697c38255ed184209d11f0436",
    "zh:a55f6fb2f998b39dad5bb107c4c1b7ff022aa54cc77fe31e98d3ae8894833ce4",
    "zh:a7509f8d1db99156bbf1b72e1acc25ccf093a8fd4af264464e1b054e90a87eb8",
    "zh:b3ad9d84fc076f71cdd1574ca417e7b565b79a2d1e7afcc5ec211f1aaa8c0227",
    "zh:f569b65999264a9416862bca5cd2a6177d94ccb0424f3a4ef424428912b9cb3c",
    "zh:fd2a9f9741792a11d7f1fa9affe080c8b40b93e5f6a0b61cb25dfcd9c87dc44e",
  ]
}
```

`terraform init` writes this file. It records the exact provider version chosen (`8.8.1`), the constraints that led to it, and `hashes`: fingerprints of the provider's package so a tampered download is refused. Commit it so everybody gets the same provider. The line `h1:` is a hash of the contents; each `zh:` is a hash of a downloadable archive. The modules have their own lock files for their tests.

## 6. Try it yourself

```bash
terraform version
```
Expected: `Terraform v1.17.0` (1.9 or newer works for this repository).

```bash
terraform fmt -check -recursive infra; echo "exit=$?"
```
Expected: `exit=0` (all files are in canonical style).

```bash
cd infra/environments/lab && terraform init -backend=false -input=false >/dev/null && terraform validate
```
Expected: `Success! The configuration is valid.`

```bash
cd infra/environments/lab && GOOGLE_OAUTH_ACCESS_TOKEN=placeholder terraform plan -input=false -lock=false -var-file=lab.tfvars.example | grep -E "^Plan"
```
Expected: `Plan: 50 to add, 0 to change, 0 to destroy.` Nothing is created. (3 folders, 4 projects, their audit settings and APIs, 4 policies, 3 test identities and their roles, the shared network and its grants, the bucket and the perimeter.)

```bash
head -8 infra/environments/lab/.terraform.lock.hcl
```
Expected: the provider address `registry.terraform.io/hashicorp/google`, `version = "8.8.1"` and the constraints `>= 8.0.0, ~> 8.8, < 9.0.0`.

## 7. Mistakes people make

- **Putting secrets in state.** State holds every attribute of every resource. This repository creates no keys and no secrets.
- **Granting broad roles on the project.** Grant on the resource (a subnet, a bucket); the Python guardrail tests fail on `roles/owner` or `roles/editor`.
- **Editing the state by hand.** Use Terraform commands.
- **Using unknown values as `for_each` keys.** Key by fixed labels (the subnet name plus the position).
- **Committing `.terraform/` or `lab.tfvars` with real ids.** `.gitignore` excludes them; only `*.tfvars.example` is tracked.
- **Not pinning the provider.** `.terraform.lock.hcl` is committed for the environment.
- **Enforcing before looking.** The default is dry run for a reason; `scripts/enforce.sh` asks you to confirm that you read the logs.
- **Running `apply` from an unknown directory.** The scripts `cd` into the environment first.

## 8. Check yourself

1. What does `terraform plan` change in the cloud? *Nothing; it only shows what apply would do.*
2. Why does `terraform init -backend=false` need no credentials? *It only downloads providers and sets up local files.*
3. What does `~> 8.8` allow? *8.8 and newer 8.x versions, not 9.0.*
4. How does `dynamic "spec"` switch a block off? *Its `for_each` is an empty list, so zero blocks are written.*
5. Why do both Terraform and the Python tool read `design/landing-zone.yaml`? *One source of truth, so the build and the checks cannot disagree.*

## 9. Further reading

- Terraform documentation (v1.17): <https://developer.hashicorp.com/terraform/docs>
- Language reference: <https://developer.hashicorp.com/terraform/language>
- `for_each`: <https://developer.hashicorp.com/terraform/language/meta-arguments/for_each>
- `yamldecode`: <https://developer.hashicorp.com/terraform/language/functions/yamldecode>
- Google provider docs (8.x): <https://registry.terraform.io/providers/hashicorp/google/latest/docs>
