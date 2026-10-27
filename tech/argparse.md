# argparse

## 1. What it is

`argparse` is Python's standard module for building command-line programs. You describe the words and flags your program accepts (`landing-zone simulate --mode dry-run`); `argparse` reads `sys.argv` (the list of words typed after the program name), checks them, converts them, fills in defaults, prints `--help` for free, and reports mistakes with a usage message and exit status 2.

## 2. Why this repository uses it

`landing-zone` is a command with several actions: `check`, `explain`, `render-policies` and `simulate`. Each action is a **subcommand** with its own arguments, which is what `argparse` subparsers are for. Two options, `--design` and `--policies`, belong to the whole program and come before the subcommand.

## 3. Where it appears

| Path | What it does |
| --- | --- |
| `src/landing_zone/interfaces/cli.py` | `_parser()` builds the parser; `main()` runs it. |
| `pyproject.toml` | `[project.scripts] landing-zone = "landing_zone.interfaces.cli:main"` makes `pip` install a `landing-zone` command that calls `main`. |
| `scripts/render-policies.sh`, `Makefile` | Call the installed command (`render-policies`, `check`, `explain`, `simulate`). |
| `tests/unit/interfaces/test_cli.py`, `tests/e2e/test_cli_process.py` | Call `main([...])` directly and the real program as a subprocess. |

## 4. How it works underneath

`ArgumentParser.parse_args(argv)` walks the words. A word that names a subcommand switches to that subcommand's parser. Positional arguments are matched in order; options (`--out build/x`) by name. The result is a `Namespace` object with one attribute per argument. If a required argument is missing, a value is not among the allowed `choices`, or a flag is unknown, `argparse` prints usage and **exits** (by raising `SystemExit(2)`).

An option with `action="store_true"` takes no value: present means `True`, absent means `False`. An option with `action="append"` can be repeated and collects every value into a list.

## 5. Walkthrough of this repository's use

`src/landing_zone/interfaces/cli.py`

```python
def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="landing-zone", description=__doc__)
    parser.add_argument("--design", type=Path, default=DESIGN)
    parser.add_argument("--policies", type=Path, default=POLICIES)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("check", help="check the design and the policies are consistent").set_defaults(handler=_check)
    commands.add_parser("explain", help="print each policy with its reason and the request it blocks").set_defaults(
        handler=_explain
    )

    render = commands.add_parser("render-policies", help="write the YAML that `gcloud org-policies set-policy` takes")
    render.add_argument("--org", required=True, help="the organization id (gcloud organizations list)")
    render.add_argument("--out", type=Path, default=Path("build/org-policies"))
    render.add_argument(
        "--dry-run", action="store_true", help="write dryRunSpec: the policy logs violations and blocks nothing"
    )
    render.add_argument(
        "--folder", action="append", default=[], metavar="NAME=ID", help="folder id for a folder-level policy"
    )
    render.set_defaults(handler=_render)

    simulate = commands.add_parser(
        "simulate", help="run design/scenarios.yaml and show which control answers each request"
    )
    simulate.add_argument("--mode", choices=[m.value for m in PerimeterMode], default=PerimeterMode.ENFORCED.value)
    simulate.add_argument("--scenarios", type=Path, default=SCENARIOS)
    simulate.set_defaults(handler=_simulate)
    return parser
```

- `argparse.ArgumentParser(prog="landing-zone", description=__doc__)` names the program; `__doc__` is the module's docstring, shown in `--help`.
- `parser.add_argument("--design", type=Path, default=DESIGN)`: a named option; `type=Path` converts the text into a `Path` object; the default is the repository's own file, so the common case needs no flag.
- `commands = parser.add_subparsers(dest="command", required=True)`: the first word after the program name must be one of the subcommands, and `required=True` makes a missing one an error.
- `commands.add_parser("check", help=...)` adds one subcommand. `.set_defaults(handler=_check)` stores the function to call on the result. `main` then runs `args.handler(args)`, so there is no long `if command == ...` chain.
- `render.add_argument("--org", required=True, ...)`: a named option that must be given.
- `"--dry-run", action="store_true"`: a flag. Dashes become underscores on the result (`args.dry_run`).
- `"--folder", action="append", default=[], metavar="NAME=ID"`: repeatable (`--folder production=123 --folder shared=456`). `metavar` is the placeholder shown in the help.
- `choices=[m.value for m in PerimeterMode]` limits `--mode` to `dry-run` and `enforced`, built from the enum so the list cannot drift from the code.

Reading input and exit status:

`src/landing_zone/interfaces/cli.py`

```python
def main(argv: Sequence[str] | None = None) -> int:
    """Run the command; returns the exit status (0 ok, 1 a check or scenario failed, 2 unreadable input)."""
    args = _parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (DomainError, OSError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
```

`argv: Sequence[str] | None = None` lets tests pass a list while the real program passes nothing (then `argparse` reads `sys.argv`). The exit status is `0` for success, `1` when a check or a scenario failed (the handlers return it), and `2` for unusable input: a named error (`DomainError`), an unreadable file (`OSError`) or a missing `--folder` id (`KeyError`). The error goes to standard error (`file=sys.stderr`), the normal output stays on standard output.

The handlers split `--folder NAME=ID` text:

`src/landing_zone/interfaces/cli.py`

```python
def _render(args: argparse.Namespace) -> int:
    folder_ids = dict(item.split("=", 1) for item in args.folder)
    policies = load_policies(args.policies)
    documents = [
        (policy.constraint, render_policy_document(policy, args.org, dry_run=args.dry_run, folder_ids=folder_ids))
        for policy in policies
    ]
    for path in write_policy_documents(args.out, documents):
        print(path)
    return 0
```

`item.split("=", 1)` cuts at the first `=` only; `dict(...)` turns the list of pairs into a lookup table.

## 6. Try it yourself

```bash
.venv/bin/landing-zone --help
```
Expected: usage with the four subcommands `{check,explain,render-policies,simulate}` and the two program-wide options `--design` and `--policies`.

```bash
.venv/bin/landing-zone simulate --mode nope; echo "exit=$?"
```
Expected: a `usage: landing-zone simulate ...` block, then `landing-zone simulate: error: argument --mode: invalid choice: 'nope' (choose from dry-run, enforced)` and `exit=2`.

```bash
.venv/bin/landing-zone --design nowhere.yaml check; echo "exit=$?"
```
Expected: `error: [Errno 2] No such file or directory: 'nowhere.yaml'` and `exit=2`. The program option comes before the subcommand.

```bash
.venv/bin/landing-zone render-policies --org 123456789012 --dry-run --out "$(mktemp -d)"
```
Expected: four paths, one per policy (`.../iam.disableServiceAccountKeyCreation.yaml`, `.../gcp.resourceLocations.yaml`, `.../storage.uniformBucketLevelAccess.yaml`, `.../compute.vmExternalIpAccess.yaml`).

```bash
.venv/bin/landing-zone simulate --mode dry-run | head -3
```
Expected: three lines that start with `ok`, the first being `ok    create a service account key in dev-app: REFUSED by org_policy (iam.disableServiceAccountKeyCreation)`.

## 7. Mistakes people make

- **Reading `sys.argv` by hand.** You lose help text and error messages.
- **Printing errors and returning 0.** Scripts then cannot tell failure from success.
- **Putting a program-wide option after the subcommand.** `landing-zone check --design x` fails because `--design` belongs to the parent parser.
- **Forgetting that exits happen inside `parse_args`.** Tests catch `SystemExit` where they test bad usage.
- **Long if/else chains for subcommands.** `set_defaults(handler=...)` is cleaner.
- **Hard-coding the allowed choices twice.** Here `choices` is built from the enum.

## 8. Check yourself

1. What does `required=True` on `add_subparsers` do? *A missing subcommand is an error.*
2. What does `action="store_true"` mean? *The flag takes no value: present is `True`, absent is `False`.*
3. How does `--dry-run` appear on the result? *As `args.dry_run`.*
4. What exit status does `argparse` use for bad usage? *2.*
5. How does `pip` create the `landing-zone` command? *From `[project.scripts]`, pointing at `main`.*

## 9. Further reading

- `argparse`: <https://docs.python.org/3.12/library/argparse.html>
- Argparse tutorial: <https://docs.python.org/3.12/howto/argparse.html>
- Entry points: <https://packaging.python.org/en/latest/specifications/entry-points/>
