#!/usr/bin/env bash
# Steps 1-5, build part: folders, projects, organization policies (dry run), the shared VPC, the bucket and the perimeter
# (dry run). Writes lab.tfvars from .env on the first run. Terraform asks before it applies.
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"
: "${BILLING_ACCOUNT:?set BILLING_ACCOUNT in .env}"
: "${OPERATOR_MEMBER:?set OPERATOR_MEMBER in .env}"

if [[ ! -f "$ENV_DIR/lab.tfvars" ]]; then
  cat >"$ENV_DIR/lab.tfvars" <<VARS
org_id           = "$ORG_ID"
billing_account  = "$BILLING_ACCOUNT"
quota_project_id = "$QUOTA_PROJECT"
name_suffix      = "$NAME_SUFFIX"
operator_member  = "$OPERATOR_MEMBER"
policy_mode      = "dry_run"
perimeter_mode   = "dry_run"
access_policy_id = "${ACCESS_POLICY_ID:-}"
VARS
  echo "wrote $ENV_DIR/lab.tfvars"
fi

cd "$ENV_DIR" || exit 1
terraform init
terraform apply -var-file=lab.tfvars
terraform output
