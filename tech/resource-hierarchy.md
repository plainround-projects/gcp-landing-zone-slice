# The resource hierarchy: organization, folders and projects

## 1. What it is

Google Cloud arranges everything you own in a tree. At the top is the **organization**, one per company domain. Under it are **folders**, which group projects (and other folders). A **project** is the unit that owns resources: buckets, VMs, networks, service accounts. It has a **project id** (text, globally unique, such as `prod-data-ab12cd`), a **project number** (digits, assigned by Google) and a **billing account** that pays for it. Policies and permissions set high in the tree are **inherited** by everything below. That is why the shape of the tree is the first design decision of a landing zone.

## 2. Why this repository uses it

The lesson's design is a small slice of a landing zone: three folders (`production`, `non-production`, `shared`) and four projects. A rule set once on the organization reaches all four projects; a rule for production alone could be set on the `production` folder. The Python tool checks that every project sits in a known folder and that exactly one project is the network host.

## 3. Where it appears

| Path | What it does |
| --- | --- |
| `design/landing-zone.yaml` | Lists the folders and the projects, each with its folder and role (`data`, `service`, `host`). |
| `infra/modules/folders/` | Creates one `google_folder` per name under the organization. |
| `infra/modules/project/` | Creates a project in its folder, with billing, no default network, audit logs and the enabled APIs. |
| `infra/environments/lab/main.tf` | Adds the suffix to project ids and picks the APIs by role. |
| `src/landing_zone/domain/design.py` | `validate_design` checks folders, projects and the single host. |
| `scripts/bootstrap.sh` | Creates the extra "quota" project outside the folders and grants the operator the organization-level roles. |

## 4. How it works underneath

- A resource has one parent: a project's parent is a folder or the organization; a folder's parent is the organization or another folder. The path from a resource to the top decides which inherited policies apply.
- Project ids are global and cannot be reused soon after deletion, which is why Terraform adds a short suffix. A deleted project is only scheduled for deletion and stays restorable for a while; the teardown script says 30 days.
- A project must be linked to a **billing account** before it can use paid services. Creating projects, folders and policies needs **organization-level roles**; the bootstrap script grants them to the operator.
- Each Google Cloud API (Compute, Storage, Logging) is **enabled per project**. An API that is not enabled returns an error, and `google_project_service` turns it on. `disable_on_destroy = false` leaves it on when Terraform removes the setting, which avoids breaking other things during teardown.
- Calls to organization-level APIs (policies, Access Context Manager) are billed to a **quota project**. This is why the provider sets `billing_project` and the scripts set `CLOUDSDK_BILLING_QUOTA_PROJECT`.

## 5. Walkthrough of this repository's use

`design/landing-zone.yaml`

```yaml
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
```

The folders have names only. Each project names its folder and its role. The role decides which APIs are enabled and whether it holds the network (`host`), the sensitive data (`data`) or a team's machines (`service`).

`infra/modules/folders/main.tf`

```hcl
resource "google_folder" "this" {
  for_each = toset(var.names)

  display_name        = each.value
  parent              = var.parent
  deletion_protection = var.deletion_protection
}
```

- `for_each = toset(var.names)` makes one folder per name. `toset` turns a list into a set so each name is a key.
- `display_name = each.value` and `parent = var.parent` (the organization, `organizations/ID`).
- `deletion_protection` comes from a variable (the provider says that when true or unset, a destroy that would delete the folder fails).

`infra/modules/project/main.tf`

```hcl
resource "google_project" "this" {
  name       = var.name
  project_id = var.project_id
  folder_id  = var.folder_id
  labels     = var.labels

  billing_account = var.billing_account

  # No default network: the shared VPC is the only network a service project uses.
  auto_create_network = false
  deletion_policy     = var.deletion_policy
}
```

- `folder_id` puts the project in its folder; `billing_account` links the payer.
- `auto_create_network = false` removes the `default` network that Google creates in new projects. The shared network is the only one a service project uses, and the default network has permissive rules.
- `deletion_policy = var.deletion_policy` defaults to `DELETE` in this lab so `terraform destroy` schedules deletion; the provider describes `PREVENT` as protection against any destroy.

`infra/modules/project/main.tf`

```hcl
resource "google_project_service" "enabled" {
  for_each = toset(var.services)

  project            = google_project.this.project_id
  service            = each.value
  disable_on_destroy = false
}
```

One setting per API in the list. The environment gives the data project Storage and Logging, the service projects Compute and Logging, and the host Compute and Logging.

The consistency rules, in Python:

`src/landing_zone/domain/design.py`

```python
    for project in design.projects:
        if project.folder not in design.folders:
            problems.append(f"project {project.name} is in unknown folder {project.folder}")

    host = design.project(design.host_project)
    if host is None:
        problems.append(f"host project {design.host_project} is not a project")
    elif host.role is not ProjectRole.HOST:
        problems.append(f"host project {host.name} must have role host")
    if sum(1 for p in design.projects if p.role is ProjectRole.HOST) != 1:
        problems.append("exactly one project must have role host")
```

A project in an unknown folder is a problem; so is a host project that is not a project, a host with the wrong role, or a design with zero or several hosts.

`tests/unit/domain/test_design.py`

```python
def test_the_host_project_must_exist_and_be_the_only_host(without, design):
    assert any("is not a project" in p for p in validate_design(without(host_project="ghost")))
    second_host = Project("net-2", "shared", ProjectRole.HOST)
    assert "exactly one project must have role host" in validate_design(
        without(projects=(*design.projects, second_host))
    )
    wrong_role = tuple(replace(p, role=ProjectRole.SERVICE) if p.name == "net-host" else p for p in design.projects)
    assert "host project net-host must have role host" in validate_design(without(projects=wrong_role))
```

## 6. Try it yourself

```bash
.venv/bin/python -c "
from pathlib import Path
from landing_zone.infrastructure.yaml_files import load_design
d = load_design(Path('design/landing-zone.yaml'))
print([(p.name, p.folder, p.role.value) for p in d.projects])"
```
Expected: `[('prod-data', 'production', 'data'), ('prod-app', 'production', 'service'), ('dev-app', 'non-production', 'service'), ('net-host', 'shared', 'host')]`

```bash
.venv/bin/python -m pytest tests/unit/domain/test_design.py -q -p no:cacheprovider
```
Expected: `9 passed`.

```bash
cd infra/modules/project && terraform init -backend=false -input=false >/dev/null && terraform test
```
Expected: `Success! 4 passed, 0 failed.`

```bash
cd infra/modules/folders && terraform init -backend=false -input=false >/dev/null && terraform test
```
Expected: `Success! 3 passed, 0 failed.`

With an organization (not run here): `gcloud resource-manager folders list --organization=ORG_ID` lists the three folders after `scripts/deploy.sh`.

## 7. Mistakes people make

- **Putting every project in one folder.** Then a rule for production alone has nowhere to sit.
- **Confusing project id, name and number.** Names can repeat; the id is global and chosen once; the number is assigned and appears in principals and perimeters.
- **Leaving the default network** in a project that should use the shared one.
- **Forgetting that APIs are per project.** The first call fails until the service is enabled.
- **Forgetting the quota project** for organization-level API calls, which then fail with a quota error.
- **Reusing a deleted project id.** Add a suffix.

## 8. Check yourself

1. What is inherited down the tree? *Policies and permissions set on a parent.*
2. Which of project id, name and number is assigned by Google? *The number.*
3. Why does the project module set `auto_create_network = false`? *The shared network is the only network these projects use.*
4. What does `google_project_service` do? *Enables one API in one project.*
5. Why does the check demand exactly one host project? *The shared network belongs to one project; two or none would make the design ambiguous.*

## 9. Further reading

- Resource hierarchy: <https://docs.cloud.google.com/resource-manager/docs/cloud-platform-resource-hierarchy>
- Creating and managing folders: <https://docs.cloud.google.com/resource-manager/docs/creating-managing-folders>
- Creating and managing projects: <https://docs.cloud.google.com/resource-manager/docs/creating-managing-projects>
- Terraform `google_project`: <https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/google_project>
