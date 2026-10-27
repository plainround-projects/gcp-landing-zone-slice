# Bash

## 1. What it is

Bash is a **shell**: a program that reads commands you type (or that a file contains) and runs other programs for you. A **shell script** is a text file of such commands. A **command** is a program name followed by **arguments** (the words after it) and **flags** (arguments that start with `-`). Bash also has variables, `if`, `for` and functions, so a script can make decisions. The scripts here need Bash (the macOS one is fine, version 3.2 or newer; they were run with 5.3).

## 2. Why this repository uses it

The runbook is a list of `gcloud` and `terraform` commands that a person runs in order: create the bootstrap project, deploy, read the dry-run logs, enforce, prove each control with a refused request, attack the perimeter, tear down. Putting them in scripts makes them exact, repeatable and checkable with `shellcheck` (see `shellcheck.md`). Two helpers, `check` and `refused`, turn a command into a PASS or FAIL line.

## 3. Where it appears

| Path | What the script does |
| --- | --- |
| `scripts/lib.sh` | Shared by the others (`source`d): loads `.env`, derives every name, defines `check` and `refused`. |
| `scripts/bootstrap.sh` | Creates the quota project, enables APIs, grants the operator the organization roles. |
| `scripts/deploy.sh` | Writes `lab.tfvars` on the first run, then `terraform init` and `apply`. |
| `scripts/render-policies.sh` | The no-Terraform route for the policies: render, `gcloud org-policies set-policy`. |
| `scripts/upload-sample.sh` | Puts `customers.csv` into the bucket. |
| `scripts/read-dry-run.sh` | Normal traffic, then the dry-run violations. |
| `scripts/enforce.sh` | Flips policies and perimeter to enforced after a typed confirmation. |
| `scripts/prove-policies.sh`, `prove-network.sh`, `attack.sh` | The proofs of steps 2, 3 and 5. |
| `scripts/prove.sh` | Runs the three proofs in order. |
| `scripts/teardown.sh` | Relaxes the perimeter, destroys, deletes the bootstrap project. |

## 4. How it works underneath

- Bash starts a program as a new **process** and waits for it. Each process has an **exit status**, a number: `0` means success, anything else means failure. `$?` holds the last one.
- **Variables** hold text. `NAME=value` sets one; `"$NAME"` reads it. **Always put quotes around expansions**: without them Bash splits the text at spaces and expands `*`.
- `$(command)` runs a command and substitutes its output. `|` (a **pipe**) sends one program's output into the next program's input. `>file` writes output to a file; `>/dev/null` throws it away; `2>&1` sends error output where normal output goes.
- `source file` runs another file's lines in the *current* shell, so its variables and functions become available. That is how `lib.sh` works, and why its `set -euo pipefail` applies to every script that sources it.
- `[[ ... ]]` is Bash's test: `-f path` (file exists), `==` (text equals; the right side can be a pattern such as `10.50.0.*`).
- Environment variables are copied into child processes if they are **exported**. `set -a` makes every variable assigned afterwards exported automatically.
- A **function** is a named group of commands. Inside it `$1`, `$2` are its arguments, `shift` drops the first one, and `"$@"` is all the rest, each kept as one word.

## 5. Walkthrough of this repository's use

### The shared header

`scripts/lib.sh`

```bash
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
```

- `#!/usr/bin/env bash` (the **shebang**) tells the system to run the file with Bash found on the PATH.
- `# shellcheck disable=SC2034` tells the linter the variables look unused here but the scripts that source this file use them.
- `set -euo pipefail` makes the script strict. `-e`: stop at the first failing command. `-u`: using an unset variable is an error. `-o pipefail`: a pipe fails if *any* stage fails.
- `ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`: `BASH_SOURCE[0]` is this file's path; `dirname` takes its folder; `/..` goes up to the repository root; `pwd` prints the absolute path. The script works from any current folder.
- `if [[ -f "$ROOT/.env" ]]; then set -a; source ...; set +a; fi` loads `.env` and exports its variables. The `# shellcheck disable=SC1091` comment tells the linter it cannot follow a file chosen at run time.
- `: "${ORG_ID:?set ORG_ID in .env (see .env.example)}"`: the `:` command does nothing, but its argument is expanded first, and `${VAR:?message}` stops the script with that message if the variable is empty or unset.
- The lines that follow build the names of the lesson from the suffix: `PROD_DATA="prod-data-$NAME_SUFFIX"`, the bucket, and the three test identities' email addresses.

### The PASS/FAIL helpers

`scripts/lib.sh`

```bash
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
```

- `export CLOUDSDK_BILLING_QUOTA_PROJECT=...` sets an environment variable that `gcloud` reads, so every call is charged to the bootstrap project (see `gcloud-cli.md`).
- `check`: `local what="$1"` keeps the first argument in a variable private to the function; `shift` removes it, so `"$@"` is the command to run. `if "$@" >/dev/null 2>&1; then` runs it silently and branches on its exit status. `FAILED=1` records a failure.
- `refused` is the lesson's key idea, written once: a request must **fail**, and it must fail *for the stated reason*. `output="$("$@" 2>&1)"` captures the command's output and error text. If the command succeeded, that is a FAIL (the control did not stop it). If it failed, `grep -q -- "$text" <<<"$output"` looks for the expected words, and `--` ends the options so a text that begins with a dash is not read as a flag. `<<<` feeds a variable to a command as its input (a **here-string**). A refusal for a different reason prints the first five lines (`head -5`) and counts as a FAIL.

### Arrays, loops and a typed confirmation

`scripts/bootstrap.sh`

```bash
ROLES=(
  roles/resourcemanager.folderAdmin
  roles/resourcemanager.projectCreator
  roles/orgpolicy.policyAdmin
  roles/compute.xpnAdmin
  roles/accesscontextmanager.policyAdmin
)
echo "Granting $OPERATOR_MEMBER these roles on organization $ORG_ID: ${ROLES[*]}"
read -r -p "Type yes to continue: " answer
[[ "$answer" == "yes" ]] || { echo "not confirmed"; exit 1; }
for role in "${ROLES[@]}"; do
  gcloud organizations add-iam-policy-binding "$ORG_ID" --member="$OPERATOR_MEMBER" --role="$role" --condition=None >/dev/null
  echo "granted $role"
done
gcloud billing accounts add-iam-policy-binding "$BILLING_ACCOUNT" --member="$OPERATOR_MEMBER" --role=roles/billing.user >/dev/null
```

- `ROLES=( ... )` is an **array**; `"${ROLES[*]}"` joins it into one text for the message, `"${ROLES[@]}"` expands to one word per item for the loop.
- `read -r -p "Type yes to continue: " answer` waits for you to type; `-r` keeps backslashes literal.
- `[[ "$answer" == "yes" ]] || { echo "not confirmed"; exit 1; }` exits unless you typed exactly `yes`. `||` means "if the left side failed, do the right side".
- `for role in "${ROLES[@]}"; do ... done` repeats the command for each role, with `--condition=None` and `>/dev/null` to keep the output short.

### A heredoc that writes a file, and a safe `cd`

`scripts/deploy.sh`

```bash
if [[ ! -f "$ENV_DIR/lab.tfvars" ]]; then
  cat >"$ENV_DIR/lab.tfvars" <<VARS
org_id           = "$ORG_ID"
billing_account  = "$BILLING_ACCOUNT"
quota_project_id = "$QUOTA_PROJECT"
name_suffix      = "$NAME_SUFFIX"
operator_member  = "$OPERATOR_MEMBER"
policy_mode      = "dry_run"
perimeter_mode   = "dry_run"
access_policy_id = "${ACCESS_POLICY_ID:-}"
VARS
  echo "wrote $ENV_DIR/lab.tfvars"
fi

cd "$ENV_DIR" || exit 1
terraform init
terraform apply -var-file=lab.tfvars
terraform output
```

- `[[ ! -f "$ENV_DIR/lab.tfvars" ]]` is true when the file does **not** exist, so the values are written only once and your edits are never overwritten.
- A **here-document** (`<<VARS` ... `VARS`) feeds the lines between the markers to `cat`, which writes them to the file. Unquoted `VARS` means `$ORG_ID` and the other variables are replaced first. `"${ACCESS_POLICY_ID:-}"` is the value or, when unset, the empty text (so `-u` does not stop the script).
- `cd "$ENV_DIR" || exit 1` stops if the folder is missing instead of running `terraform` in the wrong place.

### A choice by word

`scripts/render-policies.sh`

```bash
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
```

- `MODE="${1:-dry-run}"` takes the first argument or `dry-run`.
- `case "$MODE" in dry-run) ... ;; *) ... ;; esac` picks a branch by the text; `*` matches anything else and exits with status 2 and a usage line on standard error (`>&2`).
- `for file in "$OUT"/*.yaml; do gcloud org-policies set-policy "$file"; done` runs the command once per generated file.
- `$FLAG` is deliberately unquoted: it is empty or one word. `# shellcheck disable=SC2086` says so, with the reason.

### Running scripts that may fail, and still reporting

`scripts/prove.sh`

```bash
set -uo pipefail
DIR="$(dirname "$0")"
status=0
"$DIR/prove-policies.sh" || status=1
"$DIR/prove-network.sh" || status=1
"$DIR/attack.sh" || status=1
exit "$status"
```

This file has no `-e`. It must run all three proofs even if the first fails, so each call ends with `|| status=1` (remember the failure) and the script exits with the combined status. `"$(dirname "$0")"` is the folder of this script (`$0` is how it was started).

### A function with arguments, a glob test and a nested shell

`scripts/prove-network.sh`

```bash
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
```

- `vm() { # vm NAME PROJECT SUBNET IDENTITY` defines a function; `$1` to `$4` are its arguments and `"$REGION-b"` builds the zone name.
- The `check` lines use `bash -c "..."` because `check` needs a single command, and the inner `[[ "$(gcloud ...)" == 10.50.0.* ]]` tests that the address starts with the subnet's prefix. `\"` and `\$` keep the quote and dollar sign for the inner shell, which does the expansion.
- `refused "team-prod in team-dev's subnet" "compute.subnetworks.use" vm vm3 ...` passes the function `vm` and its arguments as the command; `refused` runs it with `"$@"`.
- The last lines delete the two test VMs, then `exit "$FAILED"` reports the verdict.

### Waiting for a change to spread

`scripts/teardown.sh`

```bash
read -r -p "Delete the lab (organization $ORG_ID, suffix $NAME_SUFFIX)? Type the suffix to confirm: " answer
[[ "$answer" == "$NAME_SUFFIX" ]] || { echo "not confirmed"; exit 1; }

cd "$ENV_DIR" || exit 1
terraform apply -refresh=false -auto-approve -var-file=lab.tfvars -var perimeter_mode=dry_run -var policy_mode=dry_run -target=module.perimeter -target=module.org_policies
echo "waiting 5 minutes for the relaxed perimeter to apply"
sleep 300
terraform destroy -var-file=lab.tfvars
gcloud projects delete "$QUOTA_PROJECT" --quiet
```

Here you must type the suffix, not just `yes`, so a habit cannot delete the wrong lab. `sleep 300` waits five minutes for the relaxed perimeter to apply before `terraform destroy`; there is no signal to poll, so waiting is the honest option.

## 6. Try it yourself

```bash
bash -n scripts/lib.sh && echo "syntax ok"
```
Expected: `syntax ok` (`-n` parses without running).

```bash
shellcheck scripts/*.sh && echo clean
```
Expected: `clean`.

```bash
bash -c 'set -euo pipefail; echo before; false; echo after'; echo "exit=$?"
```
Expected: `before` then `exit=1`. `after` never prints, which is what `-e` does.

```bash
env -u ORG_ID -u NAME_SUFFIX bash -c 'source scripts/lib.sh'; echo "exit=$?"
```
Expected: `scripts/lib.sh: line 16: ORG_ID: set ORG_ID in .env (see .env.example)` and a non-zero exit status (`exit=1` with Bash 5.3 here; the exact number differs between shells). Nothing was called in the cloud.

```bash
ORG_ID=123456789012 NAME_SUFFIX=ab12cd bash -c 'source scripts/lib.sh; echo "$QUOTA_PROJECT"; echo "$TEAM_DEV_SA"'
```
Expected: `lz-bootstrap-ab12cd` then `team-dev-tester@dev-app-ab12cd.iam.gserviceaccount.com` (this works when there is no `.env` file; a `.env` in the repository root would be loaded first).

```bash
ORG_ID=1 NAME_SUFFIX=ab12cd bash -c 'source scripts/lib.sh; check "a file exists" test -f Makefile; check "no such file" test -f nope; refused "a failing command" "denied" bash -c "echo permission denied >&2; exit 1"; refused "wrong text" "denied" bash -c "echo other >&2; exit 1"; echo "FAILED=$FAILED"'
```
Expected:
```text
PASS  a file exists
FAIL  no such file
PASS  a failing command: refused (denied)
FAIL  wrong text: refused, but not with 'denied':
other
FAILED=1
```

## 7. Mistakes people make

- **Unquoted variables** (`rm $DIR/*`) split on spaces and can delete the wrong thing. Quote everything.
- **No `set -euo pipefail`.** Scripts keep going after an error and report success. The one script without `-e` (`prove.sh`) has a reason and collects its own status.
- **Using `cd` without checking it worked.** Scripts here use `cd ... || exit 1`.
- **Treating "the request failed" as the proof.** A request can fail because a name is misspelled. `refused` demands the *reason* too.
- **Parsing `ls` output.** Use globs and loops.
- **Putting secrets on the command line.** They show up in process lists. This repository keeps no secret in a script; the identities are test service accounts without keys.
- **Relying on the current folder.** `lib.sh` computes `ROOT` from the script's own path.

## 8. Check yourself

1. What does `set -e` do? *Stops the script at the first failing command.*
2. What does `"$@"` mean in `check`? *All remaining arguments, each kept as one word.*
3. What does `${VAR:?msg}` do? *Stops with `msg` if `VAR` is empty or unset.*
4. What does `source lib.sh` do differently from running `./lib.sh`? *It runs in the current shell, so variables and functions stay available.*
5. Why does `refused` check the text of the error as well as the failure? *A command can fail for the wrong reason; the text shows which control spoke.*

## 9. Further reading

- GNU Bash manual (Bash 5.3; the scripts also run on macOS's 3.2): <https://www.gnu.org/software/bash/manual/bash.html>
- Shell parameter expansion (`:?`, `:-`): <https://www.gnu.org/software/bash/manual/bash.html#Shell-Parameter-Expansion>
- The set builtin (`-e`, `-u`, `pipefail`): <https://www.gnu.org/software/bash/manual/bash.html#The-Set-Builtin>
- ShellCheck wiki: <https://www.shellcheck.net/wiki/>
