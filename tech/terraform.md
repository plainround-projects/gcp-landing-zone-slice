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
