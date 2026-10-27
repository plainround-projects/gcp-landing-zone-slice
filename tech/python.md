# Python

## 1. What it is

Python is a programming language. You write text files that end in `.py`, and a program called the **interpreter** reads them and runs them. This repository needs Python 3.12 or newer (`requires-python = ">=3.12"`) and was tested with 3.13. A **type hint** is a note such as `name: str` that says what kind of value something holds; Python ignores it when running, and `mypy` checks that the hints fit together (see `mypy.md`). The only library the program needs at run time is PyYAML (see `pyyaml.md`); the rest is Python's **standard library**, the modules that come with the language.

## 2. Why this repository uses it

The lesson is mostly infrastructure code, but it asks a question that is easy to get wrong: *which control stops this request?* An organization policy, a subnet permission, a perimeter, or plain IAM. The Python package `landing_zone` is a small model of those four controls. It checks the design and the policies, and it answers that question for the lesson's 13 requests in code that CI can run without an organization.

## 3. Where it appears

| Path | What it does with Python |
| --- | --- |
| `src/landing_zone/domain/` | The model: `Design`, `OrgPolicy`, the request types, `Landscape` (the decision rules), `Decision`. No input or output. |
| `src/landing_zone/application/` | `check` (consistency), `render` (policy documents and the explanation table), `scenarios` (run the requests and compare the answers). |
| `src/landing_zone/infrastructure/yaml_files.py` | Reads the YAML files and writes the policy documents. |
| `src/landing_zone/interfaces/cli.py` | The `landing-zone` command. |
| `tests/` | Unit tests, one end-to-end test file and the Terraform guardrail tests. |

## 4. How it works underneath

The interpreter turns each file into **bytecode** (a compact list of simple instructions) and runs it. `import landing_zone.domain.design` makes Python search the folders on `sys.path` for that file. After `pip install -e .` (see `pip-lock-files.md`), `src/` is on that path inside the virtual environment `.venv`, so the package can be imported from anywhere.

Every value is an **object** with a type, and types are checked while the program runs. That is flexible but late: a typo shows up only when the line is reached. Type hints plus `mypy` move many of those mistakes to before the program runs.

Three words come up all the time in this code:

- A **class** is a blueprint for objects. A **dataclass** is a class whose boring parts (the constructor, the printing, the comparison) Python writes for you from the list of fields.
- An **enum** is a fixed set of named values, such as the three roles a project can have.
- A **module** is one `.py` file; a **package** is a folder of modules with an `__init__.py` file.

## 5. Walkthrough of this repository's use

### Immutable values

`src/landing_zone/domain/design.py`

```python
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from enum import Enum
```

- `from __future__ import annotations` makes Python keep type hints as text instead of evaluating them at once. It lets a hint mention a class that is defined further down.
- `import ipaddress` is a standard-library module for network addresses (see `ipaddress-and-cidr.md`).
- `from dataclasses import dataclass` and `from enum import Enum` import the two helpers used below.

`src/landing_zone/domain/design.py`

```python
class ProjectRole(Enum):
    """What a project is for."""

    DATA = "data"
    SERVICE = "service"
    HOST = "host"
```

`Enum` defines a fixed set of named values (`ProjectRole.DATA`). The text `"data"` in the YAML file is turned into one with `ProjectRole("data")`; any other text raises `ValueError`, so a typo in the design file is rejected at load time instead of causing a wrong answer later.

`src/landing_zone/domain/design.py`

```python
@dataclass(frozen=True, slots=True)
class Subnet:
    """A subnet of the shared VPC, the service project that uses it and the groups allowed to use it."""

    name: str
    cidr: ipaddress.IPv4Network
    service_project: str
    user_groups: tuple[str, ...]
```

- `@dataclass(frozen=True, slots=True)` writes `__init__`, `__repr__` and `__eq__` from the fields. `frozen=True` forbids changing a field after creation; `slots=True` stores the fields in a fixed layout, which saves memory and forbids adding attributes that are not declared.
- `ipaddress.IPv4Network` is the type of a block of addresses such as `10.50.0.0/24`.
- `tuple[str, ...]` is a tuple of any length whose items are strings. A tuple cannot change, which suits frozen objects; a list would not.

### A value that validates itself

`src/landing_zone/domain/policy.py`

```python
@dataclass(frozen=True, slots=True)
class OrgPolicy:
    """One organization policy entry of `policies/org-policies.yaml`."""

    constraint: str
    kind: PolicyKind
    level: str
    reason: str
    blocked_request: str
    instead: str
    enforce: bool = False
    allowed_values: tuple[str, ...] = ()
    deny_all: bool = False

    def __post_init__(self) -> None:
        """Reject entries that are incomplete for their kind or cannot be defended."""
        if not self.constraint or "/" in self.constraint:
            raise InvalidPolicy(f"not a constraint name: {self.constraint!r}")
        if not self.reason.strip():
            raise InvalidPolicy(f"{self.constraint}: a policy with no reason is a rule you cannot defend")
        if not self.blocked_request.strip() or not self.instead.strip():
            raise InvalidPolicy(f"{self.constraint}: name one team request it blocks and what to do instead")
        if self.level != "organization" and not self.level.startswith("folder:"):
            raise InvalidPolicy(f"{self.constraint}: level must be 'organization' or 'folder:NAME', got {self.level!r}")
        if self.kind is PolicyKind.BOOLEAN and (self.allowed_values or self.deny_all):
            raise InvalidPolicy(f"{self.constraint}: a boolean constraint takes only enforce")
        if self.kind is PolicyKind.LIST:
            if self.enforce:
                raise InvalidPolicy(
                    f"{self.constraint}: a list constraint takes allowed_values or deny_all, not enforce"
                )
            if bool(self.allowed_values) == self.deny_all:
                raise InvalidPolicy(f"{self.constraint}: give exactly one of allowed_values and deny_all")

    @property
    def folder(self) -> str | None:
        """The folder name for a folder-level policy, None for the organization."""
        return self.level.removeprefix("folder:") if self.level.startswith("folder:") else None

    def applies_to_folder(self, folder: str) -> bool:
        """An organization policy applies to every folder; a folder policy only to its own."""
        return self.folder is None or self.folder == folder
```

- Fields with `= False` or `= ()` are **defaults**; a caller may leave them out.
- `__post_init__` runs right after the automatic constructor. Every rule is an `if ...: raise InvalidPolicy(...)`. A policy with no reason cannot exist at all, so no later code has to check.
- `bool(self.allowed_values) == self.deny_all` is a compact way to say "exactly one of these two": `bool(tuple)` is true for a non-empty tuple, and the test fails when both or neither is true.
- `str.removeprefix("folder:")` removes that start of the text if it is there.
- `@property` makes `policy.folder` look like a field but run code each time it is read.
- `str | None` means "a string, or `None`" (the empty value).

### A closed set of request types and `match`

`src/landing_zone/domain/requests.py`

```python
Request = CreateServiceAccountKey | CreateBucket | CreateVm | CopyObject | ReadObject
```

`CreateServiceAccountKey | CreateBucket | ...` is a **union type**: a `Request` is any one of these five classes.

`src/landing_zone/domain/landscape.py`

```python
    def evaluate(self, request: Request) -> Decision:
        """Decide `request`. Unknown projects are treated as outside the organization (no policy, no perimeter)."""
        match request:
            case CreateServiceAccountKey():
                return self._key(request)
            case CreateBucket():
                return self._bucket(request)
            case CreateVm():
                return self._vm(request)
            case CopyObject():
                return self._copy(request)
            case ReadObject():
                return self._read(request)
```

`match request:` with `case CreateBucket():` is **structural pattern matching** (Python 3.10 and later). Each `case` checks the class of `request`; the matching branch runs. Because `Request` is a union and the function has a return type, `mypy` can report a request type that no `case` handles.

### Rules as small functions

`src/landing_zone/domain/landscape.py`

```python
def _location_allowed(location: str, allowed_values: tuple[str, ...]) -> bool:
    lowered = location.lower()
    for value in allowed_values:
        if value == _EU_LOCATION_GROUP and (lowered == "eu" or lowered.startswith("europe-")):
            return True
        if value.lower() == lowered:
            return True
    return False
```

`for ... in ...:` loops over the allowed values; `return True` ends the function at the first success; `lowered.startswith("europe-")` is a string method. The group name `in:eu-locations` is a convention of the organization-policy service for "every EU location". A name that starts with an underscore (`_location_allowed`) is a signal to readers: private to this file.

### Collecting every problem

`src/landing_zone/domain/design.py`

```python
def validate_design(design: Design) -> list[str]:
    """Return every structural problem of the design, in a stable order; an empty list means it is consistent."""
    problems: list[str] = []
    problems += _duplicates("folder", design.folders)
    problems += _duplicates("project", [p.name for p in design.projects])
    problems += _duplicates("subnet", [s.name for s in design.subnets])
    problems += _duplicates("access level", [a.name for a in design.access_levels])

    for project in design.projects:
        if project.folder not in design.folders:
            problems.append(f"project {project.name} is in unknown folder {project.folder}")

    host = design.project(design.host_project)
    if host is None:
        problems.append(f"host project {design.host_project} is not a project")
    elif host.role is not ProjectRole.HOST:
        problems.append(f"host project {host.name} must have role host")
    if sum(1 for p in design.projects if p.role is ProjectRole.HOST) != 1:
        problems.append("exactly one project must have role host")

    for subnet in design.subnets:
        service = design.project(subnet.service_project)
        if service is None or service.role is not ProjectRole.SERVICE:
            problems.append(f"subnet {subnet.name} names {subnet.service_project}, which is not a service project")
        if not subnet.user_groups:
            problems.append(f"subnet {subnet.name} has no user group, so nobody may use it")
    problems += _overlaps(design.subnets)
```

The function builds a list of messages, so one run reports every problem and not just the first. `problems += [...]` appends a list to a list. `sum(1 for p in design.projects if p.role is ProjectRole.HOST) != 1` counts with a **generator expression** (a loop written inside parentheses that produces values one by one). `is` compares identity, which is the right test for enum members. `f"..."` is an **f-string**: text with `{values}` filled in.

`src/landing_zone/domain/design.py`

```python
    def project(self, name: str) -> Project | None:
        """The project called `name`, or None when the design has none."""
        return next((p for p in self.projects if p.name == name), None)

    def subnet(self, name: str) -> Subnet | None:
        """The subnet called `name`, or None."""
        return next((s for s in self.subnets if s.name == name), None)
```

`next((p for p in self.projects if p.name == name), None)` returns the first match, or `None` when there is none.

### Comparing an answer with a promise

`src/landing_zone/application/scenarios.py`

```python
class Expectation:
    """What a scenario must produce: allowed, or refused by `control` with `detail`."""

    allowed: bool
    control: Control | None = None
    detail: str | None = None

    def matches(self, decision: Decision, *, also_logged: bool = False) -> bool:
        """True when the decision is the expected one; `also_logged` lets a dry-run log entry stand for the control."""
        if self.allowed:
            return decision.allowed
        shown = decision.stopped_by or (decision.logged_only[0] if also_logged and decision.logged_only else None)
        return (
            shown is not None and shown.control is self.control and (self.detail is None or shown.detail == self.detail)
        )
```

`decision.stopped_by or (...)` uses `or` to take the first value that is not empty. `a if cond else b` is a **conditional expression**. The keyword-only argument `*, also_logged: bool = False` (everything after the `*`) must be given by name, so a call reads `matches(decision, also_logged=True)`.

## 6. Try it yourself

```bash
.venv/bin/python --version
```
Expected: `Python 3.13.12` (any 3.12 or newer works).

```bash
.venv/bin/python -c "
from landing_zone.domain.policy import OrgPolicy, PolicyKind
try:
    OrgPolicy('a.b', PolicyKind.BOOLEAN, 'organization', '', 'req', 'instead', enforce=True)
except Exception as error:
    print(type(error).__name__, '-', error)"
```
Expected: `InvalidPolicy - a.b: a policy with no reason is a rule you cannot defend`

```bash
.venv/bin/python -c "
from pathlib import Path
from landing_zone.infrastructure.yaml_files import load_design
d = load_design(Path('design/landing-zone.yaml'))
print(d.folders); print([str(s.cidr) for s in d.subnets])"
```
Expected: `('production', 'non-production', 'shared')` then `['10.50.0.0/24', '10.60.0.0/24']`.

```bash
.venv/bin/python -c "
from landing_zone.domain.landscape import _location_allowed
print(_location_allowed('europe-west1', ('in:eu-locations',)), _location_allowed('us-central1', ('in:eu-locations',)))"
```
Expected: `True False`

```bash
.venv/bin/python -c "
from landing_zone.domain.design import ProjectRole
print(ProjectRole('data'))
try:
    ProjectRole('nope')
except ValueError as error:
    print(error)"
```
Expected: `ProjectRole.DATA` then `'nope' is not a valid ProjectRole`.

## 7. Mistakes people make

- **Mutable default arguments** (`def f(x=[])`) share one list between calls. None here: the values are frozen and the lists are built inside the functions.
- **Checking only the first problem.** `validate_design` returns them all, so a person fixes the design in one pass.
- **Forgetting a case in a `match`.** The union type lets `mypy` warn.
- **Comparing a string with an enum.** `"data" == ProjectRole.DATA` is false; convert with `ProjectRole("data")`.
- **Reading files in the model.** The domain does no input or output; an import-linter contract forbids `pathlib`, `yaml`, `json`, `argparse` and `subprocess` there (see `import-linter.md`).
- **Catching every exception.** The command catches only the named errors (`DomainError`, `OSError`, `KeyError`), so a real bug still shows its traceback.

## 8. Check yourself

1. What does `frozen=True` do? *Forbids changing a field after the object is created.*
2. What does `match request:` do? *Chooses a branch by the class of `request`.*
3. What does `bool(self.allowed_values) == self.deny_all` test? *That exactly one of the two is set.*
4. Why return a list of problems instead of raising on the first? *So one run shows everything that is wrong.*
5. What is `X | Y` in a type position? *A union: a value of either type.*

## 9. Further reading

- Python 3.12 documentation: <https://docs.python.org/3.12/>
- Structural pattern matching: <https://docs.python.org/3.12/tutorial/controlflow.html#match-statements>
- `dataclasses`: <https://docs.python.org/3.12/library/dataclasses.html>
- `enum`: <https://docs.python.org/3.12/library/enum.html>
