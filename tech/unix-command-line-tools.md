# Small command-line tools used by the scripts: grep, sed, sort, head, find, cat, rm, sleep, dirname

## 1. What it is

These are small programs that ship with macOS and Linux, each doing one job; the shell connects them. **grep** finds lines that match a pattern. **sed** edits text as it flows through. **sort** orders lines. **head** keeps the first lines. **find** searches folders. **cat** prints files (or writes them, with `>`). **rm** deletes. **sleep** waits. **dirname** gives the folder part of a path. **touch** creates an empty file or updates its time. `command -v NAME` prints where a program is, or nothing if it is missing.

## 2. Why this repository uses it

The Makefile and the runbook scripts stay short by combining these tools: list the make targets with their one-line descriptions, find the newest Python on the machine, clean build leftovers, check that an error message names the right control, and keep a printed log short.

## 3. Where it appears

| Path | Tool and use |
| --- | --- |
| `Makefile` (`help`) | `grep`, `sed` and `sort` build the target list. |
| `Makefile` (`PYTHON`) | `command -v` picks the first Python 3.13, 3.12 or 3 it finds. |
| `Makefile` (`$(STAMP)`) | `touch $@` records that the install finished. |
| `Makefile` (`clean`) | `rm -rf` and `find infra -name .terraform -type d -prune -exec rm -rf {} +`. |
| `scripts/lib.sh` | `dirname`, `cd`, `pwd`, `grep -q --`, `head -5`. |
| `scripts/read-dry-run.sh`, `attack.sh` | `head -2` keeps the sample short. |
| `scripts/teardown.sh` | `sleep 300` waits for the relaxed perimeter. |

## 4. How it works underneath

Each tool reads **standard input** (text piped in), writes **standard output**, and returns an **exit status** (0 for success; `grep` returns 1 when nothing matched and 2 when it was used wrongly). That is why they combine: `cmd1 | cmd2` sends the output of the first into the second. A **glob** such as `scripts/*.sh` is expanded by the shell itself into the list of matching files before the tool starts.

## 5. Walkthrough of this repository's use

`Makefile`

```make
help: ## list the targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/' | sort
```

- `grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST)` keeps lines that start with a target name, a colon, anything, then `## `. `-E` enables extended patterns. `$(MAKEFILE_LIST)` is make's list of the files it read.
- `sed -E 's/:.*## /\t/'` replaces the text from the first colon through `## ` with a tab. `s/old/new/` is substitute. The result is "name, tab, description".
- `sort` orders the lines alphabetically, so the help is stable.

`Makefile`

```make
PYTHON ?= $(shell command -v python3.13 || command -v python3.12 || command -v python3)
```

`command -v python3.13 || command -v python3.12 || command -v python3` tries each name in turn: `command -v` prints the path and succeeds when the program exists; `||` goes to the next only if it failed. `$(shell ...)` is make's way to run a command and use its output.

`Makefile`

```make
$(STAMP): requirements-dev.lock pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -q --require-hashes -r requirements-dev.lock
	$(VENV)/bin/pip install -q --no-deps -e .
	touch $@
```

`touch $@` creates `.venv/.installed`. `$@` is make's name for "the file this rule makes". Because the file is newer than the lock file and `pyproject.toml`, make skips the install until one of them changes.

`Makefile`

```make
clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache .coverage .import_linter_cache
	find infra -name .terraform -type d -prune -exec rm -rf {} +
```

`find infra -name .terraform -type d -prune -exec rm -rf {} +` finds directories named `.terraform` under `infra`, does not descend into them (`-prune`), and removes them. The `{} +` passes many found paths to one `rm`.

The check that a refusal has the right reason:

`scripts/lib.sh`

```bash
  elif grep -q -- "$text" <<<"$output"; then
    echo "PASS  $what: refused ($text)"
  else
    echo "FAIL  $what: refused, but not with '$text':"
    echo "$output" | head -5
```

`grep -q -- "$text" <<<"$output"` succeeds when the output contains the expected text; `-q` prints nothing, only the exit status, and `--` stops grep from reading a text that begins with a dash as an option. `head -5` shows the first five lines of an unexpected error and no more.

## 6. Try it yourself

```bash
printf 'a\nb\n' | grep -c b
```
Expected: `1`.

```bash
echo 'build: ## compile' | sed -E 's/:.*## /\t/'
```
Expected: `build<TAB>compile` (a tab between the words).

```bash
make help | head -4
```
Expected: four lines, each a target name, a tab and its description (`audit`, `check`, `deploy`, `design`, in alphabetical order).

```bash
command -v python3.13 || echo "not installed"
```
Expected: the path of Python 3.13 (for example `/opt/homebrew/bin/python3.13`) or `not installed`.

```bash
D=$(mktemp -d); mkdir -p "$D/infra/a/.terraform" "$D/infra/b"; (cd "$D" && find infra -name .terraform -type d -prune -exec rm -rf {} + ; find infra | sort); rm -r "$D"
```
Expected: `infra`, `infra/a`, `infra/b`: the `.terraform` folder is gone, the others stay.

```bash
bash -c 'grep -q "-x" <<<"a -x b"'; echo "exit=$?"
```
Expected: grep's usage text and `exit=2`. With `--` before the text (`grep -q -- "-x"`) it succeeds with `exit=0`.

## 7. Mistakes people make

- **`grep` returning 1 and `set -e` stopping the script.** In a condition that is intended; elsewhere add `|| true` deliberately.
- **`sed -i` differs between macOS and Linux.** On macOS `sed -i ''` is required.
- **`rm -rf $VAR/...` with an empty variable.** Guard it with `${VAR:?}` or avoid it.
- **Forgetting `-p` on `mkdir`.** It fails if the folder exists.
- **Using `sleep` instead of checking.** Here it is only a pause for a perimeter change, which has no completion signal to poll.
- **A text that starts with a dash passed to `grep`.** Put `--` before it.

## 8. Check yourself

1. What does `grep -q` print? *Nothing; only the exit status.*
2. What does `sort` do in the `help` target? *Puts the targets in alphabetical order.*
3. What does `-prune` do in `find`? *Does not descend into matched directories.*
4. What does `command -v NAME` tell you? *Where the program is; it fails if there is none.*
5. What is `--` for? *It ends the options, so what follows is data.*

## 9. Further reading

- GNU grep: <https://www.gnu.org/software/grep/manual/grep.html>
- GNU sed: <https://www.gnu.org/software/sed/manual/sed.html>
- GNU findutils: <https://www.gnu.org/software/findutils/manual/html_mono/find.html>
- GNU coreutils (sort, head, cat, rm, touch, sleep): <https://www.gnu.org/software/coreutils/manual/coreutils.html>
