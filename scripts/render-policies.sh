#!/usr/bin/env bash
# The lesson's own route for step 2, without Terraform: render policies/org-policies.yaml into the YAML that
# `gcloud org-policies set-policy` takes, first as a dry run, then enforced. Use this OR Terraform, not both.
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

MODE="${1:-dry-run}"
case "$MODE" in
  dry-run) FLAG="--dry-run" ;;
  enforced) FLAG="" ;;
  *) echo "usage: $0 [dry-run|enforced]" >&2; exit 2 ;;
esac

OUT="$ROOT/build/org-policies-$MODE"
# shellcheck disable=SC2086  # FLAG is empty or one word
"$ROOT/.venv/bin/landing-zone" render-policies --org "$ORG_ID" --out "$OUT" $FLAG
for file in "$OUT"/*.yaml; do
  gcloud org-policies set-policy "$file"
done
gcloud org-policies list --organization="$ORG_ID"
