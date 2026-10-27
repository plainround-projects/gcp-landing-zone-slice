#!/usr/bin/env bash
# Step 4: make normal traffic with the perimeter in dry-run mode, then read what it WOULD have blocked.
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

echo "== normal traffic: the data reader reads the object from this machine"
gcloud storage cat "gs://$BUCKET/customers.csv" --impersonate-service-account="$DATA_READER_SA" | head -2
echo "(wait a few minutes for the audit log entry)"
echo "== dry-run violations: who was affected and why"
gcloud logging read 'protoPayload.metadata.dryRun=true AND protoPayload.metadata.@type="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata"' \
  --project="$PROD_DATA" --freshness=1h --limit=10 \
  --format='value(protoPayload.authenticationInfo.principalEmail, protoPayload.metadata.violationReason)'
echo "NO_MATCHING_ACCESS_LEVEL: add an access level for the caller (office_ip_subnetworks); RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER: add the project or an ingress rule."
