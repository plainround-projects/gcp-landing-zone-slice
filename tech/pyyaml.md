# PyYAML

## 1. What it is

PyYAML is a Python library that reads and writes YAML (see `yaml.md`). `yaml.safe_load(text)` turns YAML text into Python dictionaries, lists, strings and numbers. "Safe" means it builds only plain data and never runs code hidden in the file. `yaml.safe_dump(data)` goes the other way. Version 6.0.3 is pinned in the lock files; `types-PyYAML` gives `mypy` the type information.

## 2. Why this repository uses it

It is the one library the program needs at run time: the design, the policies and the scenarios are YAML files (they are data, not code, and Terraform reads the same files). The tool loads them with PyYAML, and writes the policy documents that `gcloud org-policies set-policy` takes with `safe_dump`.

## 3. Where it appears

| Path | What it does |
| --- | --- |
| `src/landing_zone/infrastructure/yaml_files.py` | The only production file that imports it: `_load` reads, `write_policy_documents` writes. |
| `tests/unit/test_infrastructure_policy.py` | Reads the policy file back to count its entries. |
| `pyproject.toml`, `requirements.lock` | `pyyaml==6.0.3` is a run-time dependency; `types-PyYAML` is a development one. |

## 4. How it works underneath

PyYAML parses the text into a tree of nodes and converts each node to a Python object: a mapping becomes a `dict`, a sequence a `list`, a plain scalar a `str`, `int`, `float`, `bool` or `None` depending on how it looks. `safe_load` uses a restricted converter. The full `yaml.load` can construct any Python object named in the file, which lets a hostile file run code; that is why it is never used on files from outside.

`safe_dump` walks the data and writes YAML. With `sort_keys=False` it keeps the dictionary's order, so the output reads in the order the code built it (`name` first, then `spec`).

## 5. Walkthrough of this repository's use

`src/landing_zone/infrastructure/yaml_files.py`

```python
def _load(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise InvalidDesign(f"{path}: not valid YAML: {error}") from error
    if not isinstance(data, dict):
        raise InvalidDesign(f"{path}: expected a mapping at the top level")
    return data
```

- `path.read_text(encoding="utf-8")` reads the file; `yaml.safe_load` parses it.
- `except yaml.YAMLError` catches every syntax error PyYAML knows about and turns it into the program's own `InvalidDesign`, adding the file name.
- `isinstance(data, dict)` rejects a file that parses but is not a mapping at the top (for example an empty file, which loads as `None`, or a list).

The result is a plain `dict`, and the loaders walk it with ordinary indexing:

`src/landing_zone/infrastructure/yaml_files.py`

```python
def _policy(entry: Mapping[str, Any]) -> OrgPolicy:
    blocks = entry["blocks"]
    return OrgPolicy(
        constraint=str(entry["constraint"]),
        kind=PolicyKind(entry["kind"]),
        level=str(entry.get("level", "organization")),
        reason=str(entry["reason"]),
        blocked_request=str(blocks["request"]),
        instead=str(blocks["instead"]),
        enforce=bool(entry.get("enforce", False)),
        allowed_values=tuple(str(v) for v in entry.get("allowed_values", [])),
```

- `entry["constraint"]` fails with `KeyError` when the key is missing; the caller turns that into `InvalidPolicy` naming the file.
- `entry.get("level", "organization")` supplies a default for an optional key.
- `str(...)` and `bool(...)` force the type, so a number or a string typed by mistake does not slip through.

Writing a policy document:

`src/landing_zone/infrastructure/yaml_files.py`

```python
def write_policy_documents(directory: Path, documents: Sequence[tuple[str, Mapping[str, Any]]]) -> list[Path]:
    """Write each (file stem, document) as `<stem>.yaml` under `directory`, creating it; returns the paths."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for stem, document in documents:
        path = directory / f"{stem}.yaml"
        path.write_text(yaml.safe_dump(dict(document), sort_keys=False), encoding="utf-8")
        paths.append(path)
    return paths
```

`yaml.safe_dump(dict(document), sort_keys=False)` produces the text; `directory.mkdir(parents=True, exist_ok=True)` creates the folder first. `encoding="utf-8"` avoids depending on the machine's default.

## 6. Try it yourself

```bash
.venv/bin/python -c "from importlib.metadata import version; print(version('PyYAML'))"
```
Expected: `6.0.3`

```bash
.venv/bin/python -c "
import yaml
d = yaml.safe_load(open('policies/org-policies.yaml'))
print(len(d['policies']), [p['constraint'] for p in d['policies']][:2])"
```
Expected: `4 ['iam.disableServiceAccountKeyCreation', 'gcp.resourceLocations']`

```bash
.venv/bin/python -c "
import yaml
print(yaml.safe_dump({'name': 'organizations/1/policies/x', 'spec': {'rules': [{'enforce': True}]}}, sort_keys=False))"
```
Expected:
```text
name: organizations/1/policies/x
spec:
  rules:
  - enforce: true
```

```bash
.venv/bin/python -c "import yaml; print(yaml.safe_load('a: no\nb: 22:22\nc: \"22:22\"\nd: 1.10'))"
```
Expected: `{'a': False, 'b': 1342, 'c': '22:22', 'd': 1.1}`. PyYAML follows YAML 1.1: bare `no` becomes `False`, `22:22` becomes the number 1342 (a base-60 time), and `1.10` loses its zero. The quoted `"22:22"` stays text.

```bash
.venv/bin/python -c "
import yaml
print(yaml.safe_load(''))"
```
Expected: `None`. An empty file is not a mapping, which is why `_load` checks the type.

## 7. Mistakes people make

- **Using `yaml.load` without a loader.** It can construct arbitrary objects. Use `safe_load`.
- **Forgetting multi-document files.** `safe_load` fails on `---`; use `safe_load_all`.
- **Letting values change type.** Quote anything that must stay text (`no`, `on`, `22:22`, `1.10`).
- **Trusting the shape.** A parsed file can be any shape. Check the type before indexing and name the file in the error.
- **Sorting keys by accident.** `safe_dump` sorts keys unless `sort_keys=False`.

## 8. Check yourself

1. What does "safe" mean in `safe_load`? *Only plain data types are built; no code runs.*
2. What does `safe_load("")` return? *`None`.*
3. What Python type is a YAML mapping? *`dict`.*
4. Why does `_load` check `isinstance(data, dict)`? *A file can be valid YAML and still not be a mapping.*
5. What does `sort_keys=False` do? *Keeps the order the data was built in.*

## 9. Further reading

- PyYAML documentation: <https://pyyaml.org/wiki/PyYAMLDocumentation>
- YAML 1.1 specification (the version PyYAML follows): <https://yaml.org/spec/1.1/>
