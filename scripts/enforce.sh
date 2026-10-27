#!/usr/bin/env bash
# Steps 2 and 5: flip the organization policies and the perimeter from dry run to enforced. Read the dry-run logs first
# (scripts/read-dry-run.sh). Changes can take up to 30 minutes to apply; a test that "still works" proves nothing yet.
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

read -r -p "Have you read the dry-run logs and fixed the legitimate cases? Type yes to enforce: " answer
[[ "$answer" == "yes" ]] || { echo "not confirmed"; exit 1; }

cd "$ENV_DIR" || exit 1
terraform apply -var-file=lab.tfvars -var policy_mode=enforced -var perimeter_mode=enforced
echo "Enforced. After the perimeter applies, Terraform cannot read the bucket from this machine either (that is the perimeter"
echo "working): use 'terraform apply -refresh=false', or add your address to office_ip_subnetworks first."
