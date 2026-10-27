#!/usr/bin/env bash
# Relaxes the perimeter (an enforced perimeter blocks Terraform from reading the bucket), destroys everything Terraform
# made, and deletes the quota project. Projects take 30 days to be deleted for good and can be restored until then.
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

read -r -p "Delete the lab (organization $ORG_ID, suffix $NAME_SUFFIX)? Type the suffix to confirm: " answer
[[ "$answer" == "$NAME_SUFFIX" ]] || { echo "not confirmed"; exit 1; }

cd "$ENV_DIR" || exit 1
terraform apply -refresh=false -auto-approve -var-file=lab.tfvars -var perimeter_mode=dry_run -var policy_mode=dry_run -target=module.perimeter -target=module.org_policies
echo "waiting 5 minutes for the relaxed perimeter to apply"
sleep 300
terraform destroy -var-file=lab.tfvars
gcloud projects delete "$QUOTA_PROJECT" --quiet
echo "Check for leftovers outside the projects: gcloud access-context-manager policies list --organization=$ORG_ID"
