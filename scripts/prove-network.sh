#!/usr/bin/env bash
# Step 3's Done when: a VM in each service project gets an address from its own subnet, and team A cannot create
# resources in team B's subnet. Runs as the test identities, not as you.
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

vm() { # vm NAME PROJECT SUBNET IDENTITY
  gcloud compute instances create "$1" --project="$2" --zone="$REGION-b" --machine-type=e2-micro \
    --subnet="projects/$NET_HOST/regions/$REGION/subnetworks/$3" --no-address --no-service-account --no-scopes \
    --impersonate-service-account="$4"
}
address() { gcloud compute instances list --project="$1" --filter="name=$2" --format='value(networkInterfaces[0].networkIP)'; }

vm vm1 "$PROD_APP" subnet-prod "$TEAM_PROD_SA" >/dev/null
vm vm2 "$DEV_APP" subnet-dev "$TEAM_DEV_SA" >/dev/null
check "the VM in prod-app has an address in 10.50.0.0/24" bash -c "[[ \"\$(gcloud compute instances list --project='$PROD_APP' --filter='name=vm1' --format='value(networkInterfaces[0].networkIP)')\" == 10.50.0.* ]]"
check "the VM in dev-app has an address in 10.60.0.0/24" bash -c "[[ \"\$(gcloud compute instances list --project='$DEV_APP' --filter='name=vm2' --format='value(networkInterfaces[0].networkIP)')\" == 10.60.0.* ]]"
echo "prod-app vm1: $(address "$PROD_APP" vm1)   dev-app vm2: $(address "$DEV_APP" vm2)"

refused "team-prod in team-dev's subnet" "compute.subnetworks.use" vm vm3 "$PROD_APP" subnet-dev "$TEAM_PROD_SA"
refused "team-dev in team-prod's subnet" "compute.subnetworks.use" vm vm4 "$DEV_APP" subnet-prod "$TEAM_DEV_SA"

gcloud compute instances delete vm1 --project="$PROD_APP" --zone="$REGION-b" --quiet >/dev/null
gcloud compute instances delete vm2 --project="$DEV_APP" --zone="$REGION-b" --quiet >/dev/null
exit "$FAILED"
