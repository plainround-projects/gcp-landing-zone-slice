#!/usr/bin/env bash
# Shared by the runbook scripts: loads .env and derives the names the lesson uses in every command.
# shellcheck disable=SC2034  # the variables are used by the scripts that source this file
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="$ROOT/infra/environments/lab"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

: "${ORG_ID:?set ORG_ID in .env (see .env.example)}"
: "${NAME_SUFFIX:?set NAME_SUFFIX in .env}"
QUOTA_PROJECT="lz-bootstrap-$NAME_SUFFIX"
PROD_DATA="prod-data-$NAME_SUFFIX"
PROD_APP="prod-app-$NAME_SUFFIX"
DEV_APP="dev-app-$NAME_SUFFIX"
NET_HOST="net-host-$NAME_SUFFIX"
BUCKET="prod-data-sensitive-$NAME_SUFFIX"
REGION="europe-west1"
TEAM_PROD_SA="team-prod-tester@$PROD_APP.iam.gserviceaccount.com"
TEAM_DEV_SA="team-dev-tester@$DEV_APP.iam.gserviceaccount.com"
DATA_READER_SA="data-reader@$PROD_DATA.iam.gserviceaccount.com"

# Quota project for every gcloud call that needs one (organization policies, Access Context Manager).
export CLOUDSDK_BILLING_QUOTA_PROJECT="$QUOTA_PROJECT"

# check "what is proved" command...: runs the command and prints PASS or FAIL.
check() {
  local what="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "PASS  $what"
  else
    echo "FAIL  $what"
    FAILED=1
  fi
}

# refused "what is refused" "text the refusal must contain" command...: PASS only if the command fails with that text.
refused() {
  local what="$1" text="$2" output
  shift 2
  if output="$("$@" 2>&1)"; then
    echo "FAIL  $what: the command succeeded"
    FAILED=1
  elif grep -q -- "$text" <<<"$output"; then
    echo "PASS  $what: refused ($text)"
  else
    echo "FAIL  $what: refused, but not with '$text':"
    echo "$output" | head -5
    FAILED=1
  fi
}
FAILED=0
