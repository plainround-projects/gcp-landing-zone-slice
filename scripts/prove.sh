#!/usr/bin/env bash
# Runs the proofs of steps 2, 3 and 5 in order. Exit status 1 if any fails.
set -uo pipefail
DIR="$(dirname "$0")"
status=0
"$DIR/prove-policies.sh" || status=1
"$DIR/prove-network.sh" || status=1
"$DIR/attack.sh" || status=1
exit "$status"
