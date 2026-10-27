#!/usr/bin/env bash
# Creates the quota project that Terraform and gcloud are charged for organization-level calls, links billing, enables the
# APIs, and grants YOU (the operator) the organization-level roles the build needs. Run once, as an organization admin.
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"
: "${BILLING_ACCOUNT:?set BILLING_ACCOUNT in .env}"
: "${OPERATOR_MEMBER:?set OPERATOR_MEMBER in .env}"

gcloud projects create "$QUOTA_PROJECT" --organization="$ORG_ID" --labels=purpose=lab-bootstrap
gcloud billing projects link "$QUOTA_PROJECT" --billing-account="$BILLING_ACCOUNT"
gcloud services enable cloudresourcemanager.googleapis.com cloudbilling.googleapis.com serviceusage.googleapis.com \
  orgpolicy.googleapis.com accesscontextmanager.googleapis.com iam.googleapis.com --project="$QUOTA_PROJECT"

ROLES=(
  roles/resourcemanager.folderAdmin
  roles/resourcemanager.projectCreator
  roles/orgpolicy.policyAdmin
  roles/compute.xpnAdmin
  roles/accesscontextmanager.policyAdmin
)
echo "Granting $OPERATOR_MEMBER these roles on organization $ORG_ID: ${ROLES[*]}"
read -r -p "Type yes to continue: " answer
[[ "$answer" == "yes" ]] || { echo "not confirmed"; exit 1; }
for role in "${ROLES[@]}"; do
  gcloud organizations add-iam-policy-binding "$ORG_ID" --member="$OPERATOR_MEMBER" --role="$role" --condition=None >/dev/null
  echo "granted $role"
done
gcloud billing accounts add-iam-policy-binding "$BILLING_ACCOUNT" --member="$OPERATOR_MEMBER" --role=roles/billing.user >/dev/null
echo "granted roles/billing.user on the billing account"
echo "Next: scripts/deploy.sh"
