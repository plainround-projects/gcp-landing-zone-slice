#!/usr/bin/env bash
# Step 2's Done when: a key, a bucket in a disallowed region and a VM with a public IP are each refused, naming the policy.
# Needs the policies enforced (scripts/enforce.sh), plus a minute or so for them to apply.
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

refused "creating a service account key" "Key creation is not allowed" \
  gcloud iam service-accounts keys create /dev/null --iam-account="$TEAM_DEV_SA" --project="$DEV_APP"
refused "a bucket in us-central1" "constraints/gcp.resourceLocations" \
  gcloud storage buckets create "gs://$DEV_APP-us-test" --project="$DEV_APP" --location=us-central1
refused "a VM with a public IP address in dev-app" "constraints/compute.vmExternalIpAccess" \
  gcloud compute instances create vm1 --project="$DEV_APP" --zone="$REGION-b" \
    --subnet="projects/$NET_HOST/regions/$REGION/subnetworks/subnet-dev" --machine-type=e2-micro \
    --no-service-account --no-scopes --impersonate-service-account="$TEAM_DEV_SA"
refused "a bucket with per-object ACLs" "constraints/storage.uniformBucketLevelAccess" \
  gcloud storage buckets create "gs://$DEV_APP-acl-test" --project="$DEV_APP" --location="$REGION" --no-uniform-bucket-level-access

exit "$FAILED"
