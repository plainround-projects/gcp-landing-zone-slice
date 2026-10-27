# Technology notes

One file per technology this repository uses, written for a reader who has never met it. Each file explains what the thing is, why the repository uses it, where it appears, how it works, then walks through this repository's own files line by line, with commands you can run and questions to check yourself.

## Ten minutes? Read these three

1. [organization-policy.md](organization-policy.md): the rules that stop a risky request before it happens, and why they start in dry-run mode.
2. [shared-vpc-and-networking.md](shared-vpc-and-networking.md): one network, two teams, and the single grant that keeps each team in its own subnet.
3. [vpc-service-controls.md](vpc-service-controls.md): the perimeter that stops a copy IAM would have allowed.

## Reading order

**The language and how the project is built**

| File | Role |
| --- | --- |
| [python.md](python.md) | The language of the `landing-zone` tool and the tests (3.12+). |
| [yaml.md](yaml.md) | The format of the design, the policies and the scenarios. |
| [pyyaml.md](pyyaml.md) | The library that reads and writes them. |
| [ipaddress-and-cidr.md](ipaddress-and-cidr.md) | Address ranges and the overlap check. |
| [argparse.md](argparse.md) | The command-line interface of `landing-zone`. |
| [regular-expressions.md](regular-expressions.md) | Input checks in Terraform and the guardrail tests. |
| [csv.md](csv.md) | The made-up sensitive file. |
| [pyproject-toml.md](pyproject-toml.md) | `pyproject.toml` and TOML: metadata and every tool's settings. |
| [pip-lock-files.md](pip-lock-files.md) | Virtual environment, hash-pinned lock files, `uv`, `pip-audit`. |
| [make.md](make.md) | The `Makefile`. |
| [bash.md](bash.md) | The runbook scripts under `scripts/`. |
| [unix-command-line-tools.md](unix-command-line-tools.md) | `grep`, `sed`, `sort`, `find` and friends. |
| [git.md](git.md) | The history and `.gitignore`. |
| [editorconfig.md](editorconfig.md) | One formatting habit for every editor. |

**Google Cloud**

| File | Role |
| --- | --- |
| [resource-hierarchy.md](resource-hierarchy.md) | Organization, folders and projects. |
| [organization-policy.md](organization-policy.md) | The four rules of step 2. |
| [shared-vpc-and-networking.md](shared-vpc-and-networking.md) | The shared network of step 3. |
| [vpc-service-controls.md](vpc-service-controls.md) | The perimeter of steps 4 and 5. |
| [iam-and-service-accounts.md](iam-and-service-accounts.md) | Roles, bindings and impersonation. |
| [cloud-storage.md](cloud-storage.md) | The sensitive bucket. |
| [compute-engine.md](compute-engine.md) | The test VMs that prove two controls. |
| [cloud-logging-audit-logs.md](cloud-logging-audit-logs.md) | The dry-run log and the violation log. |
| [gcloud-cli.md](gcloud-cli.md) | The command-line tool the scripts use. |

**Infrastructure as code**

| File | Role |
| --- | --- |
| [terraform.md](terraform.md) | The code in `infra/`. |
| [terraform-test.md](terraform-test.md) | Offline tests with a mock provider. |
| [tflint.md](tflint.md) | Linter for the Terraform. |
| [checkov.md](checkov.md) | Security scanner and recorded exceptions. |

**Tests and quality gates**

| File | Role |
| --- | --- |
| [pytest.md](pytest.md) | The test runner and coverage. |
| [ruff.md](ruff.md) | Linter and formatter. |
| [mypy.md](mypy.md) | Type checker. |
| [import-linter.md](import-linter.md) | Enforces the layer rule. |
| [shellcheck.md](shellcheck.md) | Linter for the shell scripts. |
| [github-actions.md](github-actions.md) | The CI workflow that runs it all. |

The notes describe the code as it is. When the code changes, update the file that quotes it.
