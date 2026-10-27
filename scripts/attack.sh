#!/usr/bin/env bash
# Step 5: with full read access (the data reader holds objectViewer), try to copy the object out of the perimeter and to
# read it from a machine that matches no access level. Both must fail with a VPC Service Controls violation.
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"
: "${OUTSIDE_BUCKET:?set OUTSIDE_BUCKET in .env: a bucket in a project outside the organization}"

refused "copy to a bucket outside the perimeter" "vpcServiceControlsUniqueIdentifier" \
  gcloud storage cp "gs://$BUCKET/customers.csv" "gs://$OUTSIDE_BUCKET/" --impersonate-service-account="$DATA_READER_SA"
refused "read from a machine that matches no access level" "vpcServiceControlsUniqueIdentifier" \
  gcloud storage cat "gs://$BUCKET/customers.csv" --impersonate-service-account="$DATA_READER_SA"

echo "== the violations in the audit log (IAM would have allowed both: the principal holds objectViewer)"
gcloud logging read 'protoPayload.metadata.@type="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata" AND NOT protoPayload.metadata.dryRun=true' \
  --project="$PROD_DATA" --freshness=1h --limit=5 \
  --format='value(protoPayload.authenticationInfo.principalEmail, protoPayload.metadata.violationReason, protoPayload.metadata.vpcServiceControlsUniqueId)'
echo "Find one by its identifier: gcloud logging read 'protoPayload.metadata.vpcServiceControlsUniqueId=\"ID\"' --project=$PROD_DATA"
exit "$FAILED"
