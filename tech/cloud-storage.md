# Cloud Storage

## 1. What it is

Cloud Storage keeps files, called **objects**, in containers called **buckets**. A bucket has a globally unique name, a **location** (a region such as `europe-west1`, or a multi-region such as `EU`), and settings. An object is a name plus bytes; the slash in `a/b.csv` is just part of the name. Addresses look like `gs://BUCKET/OBJECT`. Access is controlled by IAM roles on the bucket; the settings used here are **uniform bucket-level access** (only IAM decides, no per-object ACLs), **public access prevention** (nobody can make the bucket public) and **versioning** (an overwritten or deleted object is kept as an older version).

## 2. Why this repository uses it

The lesson needs something worth protecting: a bucket in the data project holding `customers.csv`. Step 5 attacks it. The bucket is also the thing the organization policies talk about: an EU-only location, and uniform access.

## 3. Where it appears

| Path | What it does |
| --- | --- |
| `design/landing-zone.yaml` | `sensitive_data`: project `prod-data`, bucket `prod-data-sensitive`, object `customers.csv`. |
| `infra/modules/sensitive-bucket/` | Creates the bucket and the `objectViewer` binding. |
| `infra/environments/lab/main.tf` | Adds the suffix to the bucket name (names are global) and sets the location to the region. |
| `scripts/upload-sample.sh`, `read-dry-run.sh`, `attack.sh` | Copy, read and try to leak the object with `gcloud storage`. |
| `src/landing_zone/domain/requests.py` | `CreateBucket`, `CopyObject`, `ReadObject` model the requests. |
| `data/customers.csv` | The made-up object (see `csv.md`). |

## 4. How it works underneath

- Bucket names are global and shared by everyone, so they need a suffix; a name can be reused only after the old bucket is gone.
- With uniform bucket-level access, an object has no ACL of its own; the bucket's IAM policy is the whole story, so "who can read this bucket" can be answered from one place. Without it, per-object ACLs can make one object public while the bucket looks private.
- `public_access_prevention = "enforced"` refuses any attempt to grant access to `allUsers` or `allAuthenticatedUsers`.
- `force_destroy = true` lets Terraform delete a bucket that still contains objects. That suits a lab and is dangerous in production.
- A **location** is chosen at creation and cannot be changed. The organization policy `gcp.resourceLocations` checks it at that moment (see `organization-policy.md`). The bucket is in `europe-west1` (Belgium).
- Copying an object to a bucket in another project calls the Storage service about **two** projects. If the first is inside a perimeter and the second is not, VPC Service Controls refuses the call (see `vpc-service-controls.md`).
- Roles: `roles/storage.objectViewer` reads objects (and lists them) and does not write or delete.

## 5. Walkthrough of this repository's use

`infra/modules/sensitive-bucket/main.tf`

```hcl
resource "google_storage_bucket" "this" {
  #checkov:skip=CKV_GCP_62:A lab needs no separate access-log bucket; the data-access audit logs and the perimeter's violation logs record the calls that matter here
  #checkov:skip=CKV_GCP_114:Public access prevention is enforced below; checkov looks for it under another attribute name
  project  = var.project_id
  name     = var.name
  location = var.location
  labels   = var.labels

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.force_destroy

  versioning {
    enabled = true
  }
}
```

- The two `#checkov:skip=` comments record why two security checks do not apply, with a reason each (see `checkov.md`).
- `uniform_bucket_level_access = true` and `public_access_prevention = "enforced"` are the settings above.
- `versioning { enabled = true }` keeps old versions.
- `force_destroy = var.force_destroy` is set to `true` by the environment so the lab can be torn down.
- `labels` come from the environment (`environment`, `project`, `managed-by`).

`infra/environments/lab/main.tf`

```hcl
module "sensitive_bucket" {
  source = "../../modules/sensitive-bucket"

  project_id     = module.projects[local.design.sensitive_data.project].project_id
  name           = local.bucket_name
  location       = local.region
  labels         = var.labels
  force_destroy  = true
  viewer_members = { data_reader = module.lab_identities.data_reader_member }
}
```

`location = local.region` puts the bucket in `europe-west1`, inside `in:eu-locations`.

The requests, as values:

`src/landing_zone/domain/requests.py`

```python
@dataclass(frozen=True, slots=True)
class CreateBucket:
    """Create a bucket in `project` at `location` (`europe-west1`, `us-central1`, `EU`...)."""

    project: str
    location: str
    uniform_access: bool


@dataclass(frozen=True, slots=True)
class CreateVm:
    """Create a VM in `project`; `subnet` is a subnet of the shared VPC, `caller_groups` the groups of the caller."""

    project: str
    zone: str
    subnet: str | None
    external_ip: bool
    caller_groups: frozenset[str]


@dataclass(frozen=True, slots=True)
class CopyObject:
    """Copy an object from a bucket in `source_project` to one in `destination_project`."""

    caller_can_read: bool
    source_project: str
    destination_project: str


@dataclass(frozen=True, slots=True)
class ReadObject:
    """Read an object in `project`; `from_access_level` names the access level the caller's address matches, if any."""

    caller_can_read: bool
    project: str
    from_access_level: str | None
```

Uploading and reading:

`scripts/upload-sample.sh`

```bash
gcloud storage cp "$ROOT/data/customers.csv" "gs://$BUCKET/customers.csv" --impersonate-service-account="$DATA_READER_SA" 2>/dev/null \
  || gcloud storage cp "$ROOT/data/customers.csv" "gs://$BUCKET/customers.csv"
gcloud storage ls -l "gs://$BUCKET/"
```

## 6. Try it yourself

```bash
cd infra/modules/sensitive-bucket && terraform init -backend=false -input=false >/dev/null && terraform test
```
Expected: `Success! 2 passed, 0 failed.`

```bash
.venv/bin/landing-zone simulate --mode enforced | grep bucket
```
Expected: five lines: `us-central1` is `REFUSED by org_policy (gcp.resourceLocations)`; `europe-west1` is `allowed`; per-object ACLs are `REFUSED by org_policy (storage.uniformBucketLevelAccess)`; the copy to a bucket outside the organization is `REFUSED by vpc_service_controls (RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER)`; and the copy to another bucket inside the perimeter is `allowed`.

```bash
.venv/bin/python -c "
from landing_zone.domain.landscape import _location_allowed
for place in ('EU', 'europe-north1', 'us-central1'):
    print(place, _location_allowed(place, ('in:eu-locations',)))"
```
Expected: `EU True`, `europe-north1 True`, `us-central1 False`.

```bash
grep -n "public_access_prevention\|uniform_bucket_level_access\|force_destroy" infra/modules/sensitive-bucket/main.tf
```
Expected: three lines, one for each setting.

With an organization (not run here): `scripts/upload-sample.sh`, then `gcloud storage ls -l gs://prod-data-sensitive-SUFFIX/`.

## 7. Mistakes people make

- **A global name that is already taken.** Add a suffix.
- **Per-object ACLs.** They hide who can read what; keep uniform access.
- **Choosing the location by default.** It cannot be changed later.
- **`force_destroy = true` outside a lab.**
- **Assuming IAM is the only lock.** A permitted reader can still be stopped by a perimeter, and that is the point of step 5.
- **Public access.** Prevention makes an accidental grant fail.

## 8. Check yourself

1. What is an object's name? *Text; the slash is only part of it.*
2. What does uniform bucket-level access do? *Turns off per-object ACLs so the bucket's IAM policy decides.*
3. Can you move a bucket to another location? *No; choose it at creation.*
4. Why does the bucket name carry a suffix? *Names are global and must be unique.*
5. What does `objectViewer` allow? *Reading and listing objects, not writing or deleting.*

## 9. Further reading

- Cloud Storage buckets: <https://docs.cloud.google.com/storage/docs/buckets>
- Uniform bucket-level access: <https://docs.cloud.google.com/storage/docs/uniform-bucket-level-access>
- Public access prevention: <https://docs.cloud.google.com/storage/docs/public-access-prevention>
- IAM roles for Cloud Storage: <https://docs.cloud.google.com/storage/docs/access-control/iam-roles>
