# Technology notes

One file per technology this repository uses, written for a reader who has never met it. Each file explains what the thing is, why the repository uses it, where it appears, how it works, then walks through this repository's own files line by line, with commands you can run and questions to check yourself.

## Ten minutes? Read these three

1. [organization-policy.md](organization-policy.md): the rules that stop a risky request before it happens, and why they start in dry-run mode.
2. [shared-vpc-and-networking.md](shared-vpc-and-networking.md): one network, two teams, and the single grant that keeps each team in its own subnet.
3. [vpc-service-controls.md](vpc-service-controls.md): the perimeter that stops a copy IAM would have allowed.

## Never used a terminal? Start here

Every "Try it yourself" section asks you to type commands. Here is everything you need to do that.

- A **terminal** is a window where you type a line of text, press Return, and a program runs and prints its answer in the same window. On a Mac it is the Terminal app; on Windows use WSL (Windows Subsystem for Linux); on Linux every distribution has one. The text before your cursor, often ending in `$` or `%`, is the **prompt**; you do not type it.
- A **command** is the name of a program followed by **arguments**, the words that tell it what to do: `ls docs` runs the program `ls` (list files) with the argument `docs`. A word that starts with `-` or `--` is a **flag** or **option**: `--help` asks most programs to describe themselves.
- Your terminal is always "in" a folder, the **current directory**. `pwd` prints it, `cd NAME` moves into a folder, `cd ..` moves up one, and `ls` lists what is inside. Every command in these notes is meant to be run from the **root of the repository**: the folder that holds `README.md`. A **path** such as `src/app/main.py` names a file by the folders leading to it.
- `.venv/bin/python` means "the `python` program inside the folder `.venv`, inside `bin`". `.venv` is a **virtual environment**: a private folder that holds a copy of Python and the libraries this project needs, so nothing is installed into your computer's own Python. `make install` creates it.
- `|` (a **pipe**) sends the output of the command on its left into the command on its right: `ls | head -3` shows the first three lines of the listing. `>` writes output into a file instead of the screen. `&&` runs the next command only if the first succeeded. `;` runs the next one regardless.
- A program ends with an **exit status**, a number: `0` means it worked, anything else means it failed. `echo $?` prints the status of the last command. You will see `exit=0` or `exit=1` in the notes for that reason.
- Lines in the notes that start with `Expected:` say what you should see. Small differences (timing, version numbers, the order of some lines) do not matter; a different **kind** of output does.
- **Never paste a command you do not understand into a terminal with a real cloud account signed in.** Commands marked "not run here" in these notes need a Google Cloud account, an organization, Docker or a cluster; read them, do not run them until you have one.

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
| [env-files.md](env-files.md) | `.env`: your private settings for the scripts and `make`. |
| [markdown.md](markdown.md) | The READMEs, the decision records and the operating notes. |
| [mermaid.md](mermaid.md) | The diagram in `ARCHITECTURE.md`. |
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
