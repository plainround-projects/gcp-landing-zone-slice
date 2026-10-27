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
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/' | sort

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
