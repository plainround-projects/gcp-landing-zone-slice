# IAM, roles, service accounts and impersonation

## 1. What it is

**IAM** (Identity and Access Management) answers "who may do what to which thing" in Google Cloud. An **identity** is a user, a group, or a **service account** (an identity for a program or a test, not a person). A **permission** is one allowed action (`storage.objects.get`). A **role** is a named bundle of permissions. A **binding** says "this member has this role on this resource". **Impersonation** means acting as a service account without holding its key: you are allowed to ask Google for a short-lived token for that account (the role `roles/iam.serviceAccountTokenCreator` on the account), and every call then runs as the account.

## 2. Why this repository uses it

The lesson separates four controls, and IAM is the plainest of them: the fourth scenario shows a principal with no read role refused by IAM itself (`storage.objects.get`). IAM is also how the proofs are made honest. Each proof runs as the identity under test (a stand-in for a team member, or the data reader), not as the operator, so a refusal means the control worked for that identity, not that you lacked rights.

## 3. Where it appears

| Path | What it does with IAM |
| --- | --- |
| `infra/modules/lab-identities/` | Three test service accounts, `instanceAdmin` in their own project for the two team stand-ins, and `tokenCreator` for the operator on each account. |
| `infra/modules/shared-vpc/main.tf` | `roles/compute.networkUser` on a subnet (see `shared-vpc-and-networking.md`). |
| `infra/modules/sensitive-bucket/main.tf` | `roles/storage.objectViewer` on the bucket only. |
| `scripts/bootstrap.sh` | Grants the operator five organization roles and `billing.user`, after a typed confirmation. |
| `tests/unit/test_infrastructure_policy.py` | Fails if a key resource, a broad role, a public member or a project-level binding outside the lab identities appears. |
| `src/landing_zone/domain/landscape.py` | `Control.IAM` for a copy or read without a read role. |
| `scripts/*.sh` | `--impersonate-service-account=...` on the `gcloud` calls that must run as a test identity. |

## 4. How it works underneath

- Where a role is granted matters: on the **organization** or **project** it reaches everything inside; on a **bucket**, **subnet** or **service account** it reaches only that one. This repository grants on the narrowest resource that works.
- A binding names a **member** in text: `user:you@example.org`, `group:team@example.org`, `serviceAccount:NAME@PROJECT.iam.gserviceaccount.com`. Terraform's `google_*_iam_member` resources add one binding without touching the others (the `_binding` and `_policy` kinds replace more).
- A **service account key** is a downloaded file that works like a password that never expires. The organization policy `iam.disableServiceAccountKeyCreation` forbids creating them (see `organization-policy.md`), and impersonation replaces them: the caller proves who they are with their own identity, and Google issues a token that lasts about an hour.
- **Basic roles** (`owner`, `editor`) are broad bundles; predefined roles such as `objectViewer` carry only what a job needs. The tests forbid the broad ones.
- IAM and the other controls are **additive in the sense that all must agree**: an organization policy, a subnet permission, a perimeter and IAM each can refuse; the request goes through only if none does.

## 5. Walkthrough of this repository's use

`infra/modules/lab-identities/main.tf`

```hcl
# Test identities for the lesson's proofs. They hold no key. Delete them with the lab; real teams use groups.
# The operator (you) impersonates them, so every proof runs as the identity under test and not as you.

resource "google_service_account" "team_prod" {
  project      = var.prod_app_project_id
  account_id   = "team-prod-tester"
  display_name = "Stands in for a member of team-prod"
}

resource "google_service_account" "team_dev" {
  project      = var.dev_app_project_id
  account_id   = "team-dev-tester"
  display_name = "Stands in for a member of team-dev"
}

resource "google_service_account" "data_reader" {
  project      = var.data_project_id
  account_id   = "data-reader"
  display_name = "Can read the sensitive bucket; used to attack the perimeter"
}
```

- `google_service_account` creates an identity. There is no `google_service_account_key` anywhere: no key exists.
- The comment states why: the operator impersonates them, so every proof runs as the identity under test.

`infra/modules/lab-identities/main.tf`

```hcl
# A team member may create VMs in its own service project. The subnet rights come from the shared-vpc module.
resource "google_project_iam_member" "team_prod_instances" {
  project = var.prod_app_project_id
  role    = "roles/compute.instanceAdmin.v1"
  member  = "serviceAccount:${google_service_account.team_prod.email}"
}

resource "google_project_iam_member" "team_dev_instances" {
  project = var.dev_app_project_id
  role    = "roles/compute.instanceAdmin.v1"
  member  = "serviceAccount:${google_service_account.team_dev.email}"
}
```

`google_project_iam_member` adds `roles/compute.instanceAdmin.v1` for the team's stand-in on its own service project. The subnet right comes from a separate grant.

`infra/modules/lab-identities/main.tf`

```hcl
resource "google_service_account_iam_member" "operator_impersonates" {
  for_each = {
    team_prod   = google_service_account.team_prod.name
    team_dev    = google_service_account.team_dev.name
    data_reader = google_service_account.data_reader.name
  }

  service_account_id = each.value
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = var.operator_member
}
```

`service_account_id = each.value` makes the binding **on the service account itself**, giving the operator `serviceAccountTokenCreator` on each of the three accounts and on nothing else.

`infra/modules/sensitive-bucket/main.tf`

```hcl
# The data reader holds objectViewer on this bucket only. It is the principal the attack runs as: IAM allows the read.
resource "google_storage_bucket_iam_member" "viewer" {
  for_each = var.viewer_members

  bucket = google_storage_bucket.this.name
  role   = "roles/storage.objectViewer"
  member = each.value
}
```

The data reader may read objects in this bucket and nothing more: the principal the attack runs as.

The bootstrap grants, with a confirmation:

`scripts/bootstrap.sh`

```bash
ROLES=(
  roles/resourcemanager.folderAdmin
  roles/resourcemanager.projectCreator
  roles/orgpolicy.policyAdmin
  roles/compute.xpnAdmin
  roles/accesscontextmanager.policyAdmin
)
```

These are the organization roles the build needs: folders, projects, organization policies, the Shared VPC admin and Access Context Manager.

The guardrail tests:

`tests/unit/test_infrastructure_policy.py`

```python
def test_no_service_account_key_is_ever_created():
    assert _hits(r'resource\s+"google_service_account_key"') == []


@pytest.mark.parametrize("kind", PROJECT_IAM)
def test_project_level_roles_exist_only_for_the_lab_test_identities(kind):
    assert _hits(rf'resource\s+"{kind}"') in ([], ["modules/lab-identities/main.tf"])


@pytest.mark.parametrize("role", ["roles/owner", "roles/editor", "roles/compute.networkAdmin", "roles/compute.admin"])
def test_no_broad_role_appears(role):
    assert _hits(re.escape(role)) == []


def test_nothing_is_public():
    assert _hits("allUsers|allAuthenticatedUsers") == []
```

- No `google_service_account_key` resource exists.
- A project-level IAM resource (`google_project_iam_member`, `_binding`, `_policy`) may exist only in `modules/lab-identities/main.tf`.
- None of `roles/owner`, `roles/editor`, `roles/compute.networkAdmin`, `roles/compute.admin` appears.
- `allUsers` and `allAuthenticatedUsers` (anyone on the internet) appear nowhere.

How IAM appears in the simulator:

`src/landing_zone/domain/landscape.py`

```python
    def _copy(self, request: CopyObject) -> Decision:
        if not request.caller_can_read:
            return _refused(Control.IAM, "storage.objects.get", "the caller holds no role that allows the read")
```

If the caller holds no read role, the request is refused by IAM first, before the perimeter is even asked.

## 6. Try it yourself

```bash
.venv/bin/python -m pytest tests/unit/test_infrastructure_policy.py -q -p no:cacheprovider -k "broad_role or key_is_ever or public"
```
Expected: `6 passed` (the four roles, the key rule and the public-members rule).

```bash
grep -rn "role  *= \"roles/" infra --include=main.tf | sed 's/.*"roles/roles/; s/"$//' | sort
```
Expected: `roles/compute.instanceAdmin.v1` (twice), `roles/compute.networkUser`, `roles/iam.serviceAccountTokenCreator` and `roles/storage.objectViewer`.

```bash
.venv/bin/landing-zone simulate --mode enforced | tail -1
```
Expected: `ok    a principal without a read role reads customers.csv from the office: REFUSED by iam (storage.objects.get)`.

```bash
cd infra/modules/lab-identities && terraform init -backend=false -input=false >/dev/null && terraform test
```
Expected: `Success! 3 passed, 0 failed.`

```bash
grep -c "impersonate-service-account" scripts/*.sh | grep -v ":0"
```
Expected: the scripts that run as a test identity (`attack.sh`, `prove-network.sh`, `prove-policies.sh`, `read-dry-run.sh`, `upload-sample.sh`) with their counts.

## 7. Mistakes people make

- **Reading 403 as "not logged in".** The caller authenticated; some control refused. Read which one from the message.
- **Granting a broad role to make something work.** Find the missing permission and grant a narrow role on the resource.
- **Downloading a key.** Impersonate instead.
- **Granting `tokenCreator` widely.** Whoever holds it on an account can become that account.
- **Using `_binding` or `_policy` resources** where a single `_member` was meant: they can remove other people's access.
- **Testing as yourself.** The operator may be allowed things the identity under test is not.

## 8. Check yourself

1. What is a binding? *A member, a role and a resource tied together.*
2. What does impersonation avoid? *Creating and storing a service account key.*
3. Why does the operator hold `tokenCreator` on the account and not on the project? *To impersonate those three accounts only.*
4. Which broad roles do the tests forbid? *`roles/owner`, `roles/editor`, `roles/compute.networkAdmin`, `roles/compute.admin`.*
5. Why does a request pass IAM and still fail? *Another control (policy, subnet permission, perimeter) can refuse it.*

## 9. Further reading

- IAM overview: <https://docs.cloud.google.com/iam/docs/overview>
- Service account impersonation: <https://docs.cloud.google.com/iam/docs/service-account-impersonation>
- Principal identifiers: <https://docs.cloud.google.com/iam/docs/principal-identifiers>
- Terraform IAM resources: <https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/google_project_iam>
