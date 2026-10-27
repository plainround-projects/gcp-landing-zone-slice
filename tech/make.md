# Make

## 1. What it is

`make` is a command-line tool that runs named recipes from a file called `Makefile`. A **target** is a name (`test`). A **recipe** is the list of shell commands under it, each line starting with a Tab character. A target can list **prerequisites**: other targets or files that must be up to date first. Make was designed to rebuild only what changed, but it is also a handy way to give a project short, memorable commands. This repository uses GNU Make syntax; the version that ships with macOS (3.81) is enough.

## 2. Why this repository uses it

The rule for every repository here is that a reader needs only a few commands: `make install`, `make lint`, `make test`, `make validate`. Each hides a longer, exact sequence of tool calls, and the CI workflow runs the very same targets, so what you run is what CI runs.

## 3. Where it appears

| Path | What it does with Make |
| --- | --- |
| `Makefile` | All targets: install, lint, format, test, test-e2e, validate, security, audit, check, design, simulate, plan, deploy, prove, teardown, up, run, down and clean. |
| `.github/workflows/ci.yml` | Calls `make lint-python`, `make test-terraform` and the other targets. |

## 4. How it works underneath

Make reads the whole file, builds a graph of targets and prerequisites, and then runs the recipes needed for the target you asked for, prerequisites first. For each recipe line it starts a new shell (`/bin/sh`), so a `cd` on one line does not carry to the next. If any line exits with a non-zero status Make stops and reports `Error`.

If a target name is also a **file** and that file is newer than its prerequisites, Make skips the recipe. Targets that are only commands, not files, are listed under `.PHONY` so Make always runs them. The one real file target here is `.venv/.installed`, a **stamp file**: it only records "the environment was installed", and it depends on `requirements-dev.lock` and `pyproject.toml`, so editing either makes Make rebuild the environment next time.

## 5. Walkthrough of this repository's use

### Variables and settings

`Makefile`

```make
PYTHON ?= $(shell command -v python3.13 || command -v python3.12 || command -v python3)
VENV := .venv
PY := $(VENV)/bin/python
STAMP := $(VENV)/.installed
ENV_DIR := infra/environments/lab
TF ?= terraform

-include .env
export
```

- `NAME ?= value` sets the variable only if it is not already set, so you can override it: `make PYTHON=python3.12 install`.
- `$(shell command -v python3.13 || command -v python3.12 || command -v python3)` runs a shell command while reading the file; it picks the first Python found. `command -v` prints a program's path if it exists.
- `NAME := value` evaluates once, immediately; plain `=` would re-evaluate each use.
- `-include .env` reads `.env` if it exists (the leading `-` means "do not fail if missing"), and `export` passes all variables to the commands.
- `.PHONY: ...` lists the targets that are commands, not files.

### Self-documenting help

`Makefile`

```make
help: ## list the targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/' | sort
```

Targets whose line ends with `## text` are described by this recipe. `$(MAKEFILE_LIST)` is the list of Makefiles read. `grep` keeps lines that start with a target name and contain `## `; `sed` swaps `:...## ` for a tab; `sort` orders them. A leading `@` in a recipe line stops Make from printing the command itself. This produced the output `make help` shows.

### The stamp file

`Makefile`

```make
$(STAMP): requirements-dev.lock pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -q --require-hashes -r requirements-dev.lock
	$(VENV)/bin/pip install -q --no-deps -e .
	touch $@
```

- `$(STAMP)` expands to `.venv/.installed`. The line says "to make this file, first you need these two files".
- The recipe creates the virtual environment, installs the locked packages (`--require-hashes` makes pip check every download's hash; see `pip-lock-files.md`), installs the project itself in editable mode without dependencies, and `touch $@` creates the stamp. `$@` is "the target being built".
- Targets like `lint-python: $(STAMP)` therefore install the environment first only when it is missing or out of date.

### Test targets and shell loops

`Makefile`

```make
test-terraform:
	@for dir in infra/modules/* $(ENV_DIR); do \
	  if [ -d $$dir/tests ]; then \
	    echo "== $$dir"; \
	    (cd $$dir && $(TF) init -backend=false -input=false >/dev/null && $(TF) test) || exit 1; \
	  fi; \
	done
```

- `@for dir in ...; do ... done` is one shell command spread over lines with a trailing `\`.
- `$$dir` — a doubled dollar sign passes a single `$` to the shell. Make would otherwise treat `$dir` as its own variable.
- `(cd $$dir && $(TF) init ... && $(TF) test) || exit 1` runs in a subshell so the `cd` does not leak; if it fails the loop stops with status 1.

### Calling Make from Make

`Makefile`

```make
validate-terraform:
	@for dir in infra/modules/* $(ENV_DIR); do \
	  echo "== $$dir"; \
	  (cd $$dir && $(TF) init -backend=false -input=false >/dev/null && $(TF) validate) || exit 1; \
	done
	$(MAKE) --no-print-directory plan
```

`$(MAKE)` is Make itself, so a recipe can run another target. `--no-print-directory` hides the "Entering directory" lines.

### Aggregates and ordering

`Makefile`

```make
check: lint test validate ## everything that needs no cluster and no cloud
```

`check` has no recipe; it only has prerequisites, so it runs `lint`, `test` and `validate` in that order. You can also name several targets on one command line: `make test-python test-e2e`.

## Every target of this Makefile, one by one

The whole file, then each target in turn. A target line has the form `name: prerequisites ## description`. Everything after `##` is only a comment that the `help` target prints. A recipe line starts with a Tab; a leading `@` hides the command itself and shows only its output.

`Makefile`

```make
# make help lists every target. Nothing here needs a Google Cloud account except bootstrap, deploy, enforce, prove and teardown.
PYTHON ?= $(shell command -v python3.13 || command -v python3.12 || command -v python3)
VENV := .venv
PY := $(VENV)/bin/python
STAMP := $(VENV)/.installed
ENV_DIR := infra/environments/lab
TF ?= terraform

-include .env
export

.PHONY: help install lint lint-python lint-terraform format test test-python test-terraform test-e2e \
        validate validate-terraform plan security audit check design simulate clean deploy prove teardown up run down

help: ## list the targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/' | sort

$(STAMP): requirements-dev.lock pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -q --require-hashes -r requirements-dev.lock
	$(VENV)/bin/pip install -q --no-deps -e .
	touch $@

install: $(STAMP) ## create .venv from the lock file

lint: lint-python lint-terraform ## Python (ruff, mypy, import rules), shell, Terraform format and tflint

lint-python: $(STAMP)
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .
	$(VENV)/bin/mypy
	$(VENV)/bin/lint-imports
	shellcheck scripts/*.sh

lint-terraform:
	$(TF) fmt -check -recursive -diff infra
	cd infra && tflint --init >/dev/null && tflint --recursive --config "$$PWD/.tflint.hcl"

format: $(STAMP) ## apply ruff and terraform fmt
	$(VENV)/bin/ruff check --fix .
	$(VENV)/bin/ruff format .
	$(TF) fmt -recursive infra

# The design checks, the decision rules, the scenarios and the Terraform guardrails; no organization, no cloud account.
test: test-python test-terraform ## unit tests with coverage, then the Terraform tests with a mock provider

test-python: $(STAMP)
	$(PY) -m pytest tests/unit --cov=landing_zone --cov-report=term
	$(PY) -m coverage report --include='src/landing_zone/domain/*,src/landing_zone/application/*' --fail-under=95

test-e2e: $(STAMP) ## the command-line program as a subprocess over the repository's own design files
	$(PY) -m pytest tests/e2e -m e2e

test-terraform:
	@for dir in infra/modules/* $(ENV_DIR); do \
	  if [ -d $$dir/tests ]; then \
	    echo "== $$dir"; \
	    (cd $$dir && $(TF) init -backend=false -input=false >/dev/null && $(TF) test) || exit 1; \
	  fi; \
	done

validate: validate-terraform security ## terraform init -backend=false, validate, an offline plan, and checkov

validate-terraform:
	@for dir in infra/modules/* $(ENV_DIR); do \
	  echo "== $$dir"; \
	  (cd $$dir && $(TF) init -backend=false -input=false >/dev/null && $(TF) validate) || exit 1; \
	done
	$(MAKE) --no-print-directory plan

# The plan needs no credentials: nothing in the configuration reads from Google Cloud, so a placeholder token is enough.
plan:
	cd $(ENV_DIR) && GOOGLE_OAUTH_ACCESS_TOKEN=offline-placeholder $(TF) plan -input=false -lock=false \
	  -var-file=lab.tfvars.example

security: ## checkov over the Terraform and the workflow
	checkov --config-file .checkov.yaml

audit: $(STAMP) ## check the locked dependencies for known vulnerabilities
	$(VENV)/bin/pip-audit --no-deps --disable-pip -r requirements-dev.lock

check: lint test validate ## everything that needs no cluster and no cloud

design: $(STAMP) ## check the design and the policies, and print each policy with its reason and the request it blocks
	$(VENV)/bin/landing-zone check
	$(VENV)/bin/landing-zone explain

simulate: $(STAMP) ## which control answers each of the lesson's requests, with the perimeter in dry-run and then enforced
	$(VENV)/bin/landing-zone simulate --mode dry-run
	$(VENV)/bin/landing-zone simulate --mode enforced

deploy: ## terraform apply with the policies and the perimeter in dry-run mode (needs the organization)
	scripts/deploy.sh

up: deploy ## alias of deploy (needs the organization)

run: design simulate ## check the design, then answer the lesson's requests in dry-run and enforced mode (no organization needed)

prove: ## the runbook checks for Done when steps 2 to 5 (needs the organization)
	scripts/prove.sh

teardown: ## destroy everything Terraform made and delete the bootstrap project (needs the organization)
	scripts/teardown.sh

down: teardown ## alias of teardown (needs the organization)

clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache .coverage .import_linter_cache
	find infra -name .terraform -type d -prune -exec rm -rf {} +
```

- Line 1 is a comment: nothing here needs a cloud account except the targets that talk to an organization (`bootstrap` is a script; the Makefile has `deploy`, `prove`, `teardown` and their aliases).
- `PYTHON ?= ...` picks the newest Python 3.13, 3.12 or 3 on your machine. `VENV := .venv`, `PY := $(VENV)/bin/python`, `STAMP := $(VENV)/.installed` are names used below. `ENV_DIR` is the Terraform environment; `TF ?= terraform` lets you use another binary (`make TF=tofu ...`).
- `-include .env` loads your private settings if the file exists, and `export` makes them visible to the scripts that `make` starts (the scripts also load `.env` themselves).
- `.PHONY` lists the targets that are commands and not files, so `make` always runs them.
- `help`: prints each documented target and its description, sorted (explained in `unix-command-line-tools.md`).
- `$(STAMP)`: creates `.venv`, installs the locked packages with `--require-hashes -r requirements-dev.lock` (every download is checked against its hash), installs this project with `-e .` (editable: the installed command runs the code in `src/`) and `--no-deps` (the lock file already holds every dependency), then `touch $@` creates the stamp file. The stamp's prerequisites are the lock file and `pyproject.toml`, so a change to either re-runs the install.
- `install`: only depends on the stamp, so it is the "make sure the environment exists" target.
- `lint`: depends on `lint-python` and `lint-terraform`, so it runs both.
- `lint-python`: depends on the stamp, then runs `ruff check .` (style and mistakes), `ruff format --check .` (is the formatting canonical), `mypy` (types), `lint-imports` (the layer rules) and `shellcheck scripts/*.sh` (the shell scripts). Each is a separate line: the first non-zero exit stops the target.
- `lint-terraform`: `terraform fmt -check -recursive -diff infra` prints the difference if any file is not in canonical style; the second line runs inside `infra` (`cd infra && ...` on one line, because each line is a new shell): `tflint --init >/dev/null` downloads the rule plug-in quietly and `tflint --recursive --config "$$PWD/.tflint.hcl"` checks every module with the one configuration file. `$$PWD` is the current folder; the doubled `$` hands one `$` to the shell.
- `format`: the fixing version: `ruff check --fix`, `ruff format`, `terraform fmt -recursive`.
- `test`: depends on `test-python` and `test-terraform`; the comment above it says what is covered and that no cloud is needed.
- `test-python`: `pytest tests/unit --cov=landing_zone --cov-report=term` runs the unit tests and measures coverage; the second line `coverage report --include=... --fail-under=95` fails if the domain and application layers are below 95 percent (see `pytest.md`).
- `test-e2e`: runs only the tests marked `e2e` (`-m e2e`): the program as a subprocess.
- `test-terraform`: loops over the modules and the environment; where a `tests/` folder exists it runs `terraform init -backend=false -input=false` quietly then `terraform test`. `|| exit 1` stops at the first failure. `echo "== $$dir"` prints a heading.
- `validate`: depends on `validate-terraform` and `security`.
- `validate-terraform`: the same loop with `terraform validate`, then `$(MAKE) --no-print-directory plan` starts `make` again for the target `plan`; `$(MAKE)` is always the right way to call make from make.
- `plan`: `GOOGLE_OAUTH_ACCESS_TOKEN=offline-placeholder` sets an environment variable for this one command: the Google provider insists on having a token before it starts, and nothing in the configuration reads from Google Cloud while planning, so a placeholder is enough. `-input=false` means "never ask a question", `-lock=false` skips state locking (there is no remote state), `-var-file=lab.tfvars.example` supplies the example values. The trailing `\` joins the next line.
- `security`: `checkov --config-file .checkov.yaml` (see `checkov.md`).
- `audit`: `pip-audit --no-deps --disable-pip -r requirements-dev.lock` checks the exact pinned versions against a database of known vulnerabilities, without letting pip resolve anything.
- `check`: depends on `lint`, `test` and `validate`: everything that needs no cloud.
- `design`: `landing-zone check` then `landing-zone explain`.
- `simulate`: `landing-zone simulate` twice, `--mode dry-run` then `--mode enforced`, so you see both answers.
- `deploy`: runs `scripts/deploy.sh`; `up` depends on `deploy` (an alias, because the repository rules ask for `make up`). `prove` runs `scripts/prove.sh`. `teardown` runs `scripts/teardown.sh`; `down` depends on `teardown`.
- `run`: depends on `design` and `simulate`: the one command that shows the project working with no organization at all.
- `clean`: removes the environment and the tool caches with `rm -rf`, and the downloaded Terraform plug-ins with `find ... -prune -exec rm -rf {} +` (explained in `unix-command-line-tools.md`).

## 6. Try it yourself

```bash
make help
```
Expected: one line per documented target (`audit`, `check`, ... `validate`), each followed by its description.

```bash
make -n lint-python
```
Expected (`-n` prints the commands without running them):
```text
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/lint-imports
shellcheck scripts/*.sh
```
(If `.venv/.installed` is missing, or older than `pyproject.toml` or the lock file, you will first see the install commands.)

```bash
make -n check | head -5
```
Expected: the lint commands of `check` come first.

```bash
touch pyproject.toml && make -n install | head -3
```
Expected: the install commands appear because `pyproject.toml` is now newer than the stamp.

## 7. Mistakes people make

- **Spaces instead of a Tab** in a recipe: `*** missing separator`. The `.editorconfig` in this repository forces tabs in Makefiles.
- **Forgetting `.PHONY`.** A file called `test` would make `make test` say "up to date".
- **Assuming `cd` carries to the next line.** Each line is a new shell; chain with `&&`.
- **Single `$` in shell loops.** Use `$$`.
- **Expecting `make` to stop on a failing command inside a pipe.** Use `set -o pipefail` or avoid pipes in recipes.

## 8. Check yourself

1. What starts every recipe line? *A Tab character.*
2. What is `.venv/.installed` for? *A stamp so installing only repeats when the lock file or `pyproject.toml` changes.*
3. Why `$$dir` in a recipe? *Make turns `$$` into `$` for the shell.*
4. What does `?=` do? *Sets a variable only if it has no value yet.*
5. What does `make -n` do? *Prints the commands without running them.*

## 9. Further reading

- GNU Make manual: <https://www.gnu.org/software/make/manual/make.html>
- Recipe syntax and `$$`: <https://www.gnu.org/software/make/manual/make.html#Recipes>
- Phony targets: <https://www.gnu.org/software/make/manual/make.html#Phony-Targets>
