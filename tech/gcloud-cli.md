# gcloud (the Google Cloud command-line tool)

## 1. What it is

`gcloud` is a program you run in a terminal to control Google Cloud: create projects, read logs, change permissions, copy files. Each command is a sentence of nouns and a verb, such as `gcloud storage buckets create`. It signs in as you (or as a service account you **impersonate**) and sends the matching requests to Google's APIs. The version used here is Google Cloud SDK 563.0.0.

## 2. Why this repository uses it

Terraform builds the infrastructure. `gcloud` is what the operator types to **prove** it: try the forbidden request, read the log, copy the file, attack the perimeter. The proofs need real requests answered by the real service, which is exactly what a command-line client sends.

## 3. Where it appears

| Path | What it does with gcloud |
| --- | --- |
| `scripts/lib.sh` | Sets `CLOUDSDK_BILLING_QUOTA_PROJECT` so every call is billed to the bootstrap project. |
| `scripts/bootstrap.sh` | `projects create`, `billing projects link`, `services enable`, `organizations add-iam-policy-binding`, `billing accounts add-iam-policy-binding`. |
| `scripts/render-policies.sh` | `org-policies set-policy`, `org-policies list`. |
| `scripts/upload-sample.sh`, `read-dry-run.sh` | `storage cp`, `storage ls -l`, `storage cat`. |
| `scripts/prove-policies.sh` | `iam service-accounts keys create`, `storage buckets create`, `compute instances create`. |
| `scripts/prove-network.sh` | `compute instances create`, `list`, `delete`. |
| `scripts/attack.sh`, `read-dry-run.sh` | `storage cp`, `storage cat`, `logging read`. |
| `scripts/teardown.sh` | `projects delete`; the leftovers hint uses `access-context-manager policies list`. |

None of these ran against a real organization when the repository was built (see the README's verification section).

## 4. How it works underneath

- **Configuration and credentials.** `gcloud auth login` stores your login; commands send your token. `gcloud config set project ID` stores a default project, which a command overrides with `--project`.
- **Impersonation.** `--impersonate-service-account=EMAIL` makes the command run with a short-lived token for that account. It works only if you hold `roles/iam.serviceAccountTokenCreator` on it (see `iam-and-service-accounts.md`).
- **Quota project.** Some APIs (organization policy, Access Context Manager) bill a project. The environment variable `CLOUDSDK_BILLING_QUOTA_PROJECT` names it for every command.
- **Output control.** `--format='value(field)'` prints just a field (`value(a, b)` prints two, separated by a tab); `--filter` selects rows; `--quiet` skips questions.
- **Exit status.** A failed command exits non-zero, which the `check` and `refused` helpers use to decide pass or fail (see `bash.md`).
- A refusal goes to standard error and starts with the HTTP-style name of the problem. The scripts match on the control's name inside it.

## 5. Walkthrough of this repository's use

`scripts/bootstrap.sh`

```bash
gcloud projects create "$QUOTA_PROJECT" --organization="$ORG_ID" --labels=purpose=lab-bootstrap
gcloud billing projects link "$QUOTA_PROJECT" --billing-account="$BILLING_ACCOUNT"
gcloud services enable cloudresourcemanager.googleapis.com cloudbilling.googleapis.com serviceusage.googleapis.com \
```

- `projects create ID --organization=ORG --labels=purpose=lab-bootstrap`: a project under the organization, with a label.
- `billing projects link ID --billing-account=ACCOUNT`: attaches the payer.
- `services enable A B C ... --project=ID`: turns on the listed APIs in that project.

The organization grant, after the confirmation:

`scripts/bootstrap.sh`

```bash
for role in "${ROLES[@]}"; do
  gcloud organizations add-iam-policy-binding "$ORG_ID" --member="$OPERATOR_MEMBER" --role="$role" --condition=None >/dev/null
  echo "granted $role"
done
gcloud billing accounts add-iam-policy-binding "$BILLING_ACCOUNT" --member="$OPERATOR_MEMBER" --role=roles/billing.user >/dev/null
echo "granted roles/billing.user on the billing account"
```

`organizations add-iam-policy-binding ORG --member=... --role=... --condition=None` adds one binding on the organization. `--condition=None` says the binding has no condition, which stops the command from asking.

The no-Terraform route for policies:

`scripts/render-policies.sh`

```bash
for file in "$OUT"/*.yaml; do
  gcloud org-policies set-policy "$file"
done
gcloud org-policies list --organization="$ORG_ID"
```

`org-policies set-policy FILE` applies the YAML document that the Python tool rendered; `org-policies list --organization=ID` lists what is set.

A proof that must be refused:

`scripts/prove-policies.sh`

```bash
refused "creating a service account key" "Key creation is not allowed" \
  gcloud iam service-accounts keys create /dev/null --iam-account="$TEAM_DEV_SA" --project="$DEV_APP"
refused "a bucket in us-central1" "constraints/gcp.resourceLocations" \
```

`iam service-accounts keys create /dev/null --iam-account=EMAIL` asks for a key and discards it; the policy refuses first. `storage buckets create gs://NAME --location=us-central1` tries a bucket outside the EU.

Running as an identity, and cleaning up:

`scripts/prove-network.sh`

```bash
gcloud compute instances delete vm1 --project="$PROD_APP" --zone="$REGION-b" --quiet >/dev/null
gcloud compute instances delete vm2 --project="$DEV_APP" --zone="$REGION-b" --quiet >/dev/null
```

`--zone`, `--project` and `--quiet` (no "are you sure?") make the command run unattended.

## 6. Try it yourself

You can read the commands without an account:

```bash
grep -rh "gcloud " scripts/*.sh | wc -l
```
Expected: `31` (lines that mention the tool, including comments and hints).

```bash
shellcheck scripts/*.sh && echo clean
```
Expected: `clean`.

```bash
gcloud --version | head -1
```
Expected: `Google Cloud SDK 563.0.0` (any recent version works for reading the scripts).

```bash
gcloud storage cp --help | head -3
```
Expected: `NAME`, then `gcloud storage cp - upload, download, and copy Cloud Storage objects`.

With an organization and a bootstrap project (these only read):

```bash
gcloud config list
gcloud org-policies list --organization="$ORG_ID"
```
Expected: your configuration, then the policies set on the organization.

## 7. Mistakes people make

- **Running against the wrong project or organization.** Check `gcloud config list`; the scripts take names from `.env`.
- **Forgetting the quota project** for organization-level calls.
- **Testing as yourself.** Add `--impersonate-service-account` when the identity matters.
- **Testing right after a change.** Policies and perimeters take time to apply.
- **Parsing human-readable output.** Use `--format`.
- **Putting a secret on the command line.** Nothing here needs one.

## 8. Check yourself

1. What does `--impersonate-service-account` do? *Runs the command with a short-lived token of that service account.*
2. What does `CLOUDSDK_BILLING_QUOTA_PROJECT` set? *The project charged for APIs that need one.*
3. What does `--format='value(a)'` print? *Only the field `a`.*
4. What does `--condition=None` mean? *The binding has no condition.*
5. Why do the scripts run `gcloud storage cp` as `data-reader`? *To prove what that identity, not the operator, can do.*

## 9. Further reading

- gcloud CLI overview: <https://docs.cloud.google.com/sdk/gcloud>
- Reference: <https://docs.cloud.google.com/sdk/gcloud/reference>
- Formatting output: <https://docs.cloud.google.com/sdk/gcloud/reference/topic/formats>
- Filters: <https://docs.cloud.google.com/sdk/gcloud/reference/topic/filters>
