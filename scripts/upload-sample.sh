#!/usr/bin/env bash
# Puts the made-up customers.csv into the sensitive bucket. Run before you enforce the perimeter: afterwards a laptop
# outside the access level cannot write to the bucket either.
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

gcloud storage cp "$ROOT/data/customers.csv" "gs://$BUCKET/customers.csv" --impersonate-service-account="$DATA_READER_SA" 2>/dev/null \
  || gcloud storage cp "$ROOT/data/customers.csv" "gs://$BUCKET/customers.csv"
gcloud storage ls -l "gs://$BUCKET/"
