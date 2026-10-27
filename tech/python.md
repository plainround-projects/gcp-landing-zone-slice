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

## Every module, in the order a request travels

The sections above explain Python's features one at a time. This part goes through every file of the package, whole, so that nothing is skipped. The package lives in `src/landing_zone/`. The folders are layers (see `import-linter.md`): `domain` knows nothing about files or the command line, `application` combines domain pieces into jobs, `infrastructure` talks to files, `interfaces` talks to the user.

First, a few words you will meet in every file.

- A **terminal** is a window where you type a command and press Return. The program prints its answer in the same window. A **command** such as `.venv/bin/landing-zone check` is a program's path followed by **arguments**.
- A **directory** is a folder. A **path** is the text that names a file, such as `src/landing_zone/domain/design.py`. A path that does not start with a slash is **relative**: it starts from the folder you are in.
- A **virtual environment** is a private folder (here `.venv/`) that holds its own copy of Python and of the libraries this project needs, so installing them cannot disturb anything else on your computer. `.venv/bin/python` is that private Python.
- A **docstring** is a text in triple quotes as the first thing in a file, class or function. Python keeps it as the thing's documentation; tools and `help()` show it. A class or function whose body is only a docstring is a valid, empty one.
- An **exception** is Python's way of stopping normal flow when something went wrong. `raise` starts one; `except` catches it. If nobody catches it, the program stops and prints a **traceback** (the list of calls that led to the error).

### `__init__.py` files

Each folder has an `__init__.py`. Its presence turns the folder into a **package**, which means `import landing_zone.domain` works. The files are almost empty:

`src/landing_zone/__init__.py`

```python
"""Check a landing-zone design as code and simulate which control stops a request."""
```

`src/landing_zone/application/__init__.py`

```python
"""Application layer: design checks, policy rendering and scenario runs."""
```

Only a docstring. The `domain`, `infrastructure` and `interfaces` ones are the same kind of file. The three test folders also hold an empty `__init__.py` for the same reason (so pytest treats each folder as a package and gives every test file a unique name).

### `domain/errors.py`: the names of the things that can go wrong

`src/landing_zone/domain/errors.py`

```python
"""Named errors of the domain."""


class DomainError(Exception):
    """Base class for every error the domain raises."""


class InvalidDesign(DomainError):
    """The design file is not a well-formed description of a landing zone."""


class InvalidPolicy(DomainError):
    """A policy entry is incomplete or contradicts its own kind."""


class InvalidRequest(DomainError):
    """A request or scenario cannot be understood."""
```

- `class DomainError(Exception):` defines a new kind of exception that **inherits** from the built-in `Exception`. Inheriting means "is a kind of": anything that catches `Exception` also catches a `DomainError`.
- The three classes below inherit from `DomainError`. Code can therefore catch all the program's own errors with one `except DomainError`, or only one kind. The command-line program does the first (see `argparse.md`).
- Each class has only a docstring as its body. The name carries the meaning: `InvalidDesign` (the design file is wrong), `InvalidPolicy` (a policy entry is wrong), `InvalidRequest` (a scenario cannot be understood).

### `domain/decision.py`: the answer to "who stops this request?"

`src/landing_zone/domain/decision.py`

```python
"""Which control stops a request: the answer and the evidence, as values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Control(Enum):
    """The four things that can stop a request in this landing zone."""

    ORG_POLICY = "org_policy"
    SHARED_VPC_IAM = "shared_vpc_iam"
    VPC_SERVICE_CONTROLS = "vpc_service_controls"
    IAM = "iam"


class PerimeterMode(Enum):
    """A dry-run perimeter logs violations; an enforced one refuses the call."""

    DRY_RUN = "dry-run"
    ENFORCED = "enforced"


@dataclass(frozen=True, slots=True)
class Violation:
    """One control that objects: which one, the constraint, permission or reason code, and the message it gives."""

    control: Control
    detail: str
    message: str


@dataclass(frozen=True, slots=True)
class Decision:
    """The outcome for one request. `logged_only` holds dry-run violations that were recorded but did not block."""

    violations: tuple[Violation, ...] = ()
    logged_only: tuple[Violation, ...] = ()

    @property
    def allowed(self) -> bool:
        """True when no control refuses the request."""
        return not self.violations

    @property
    def stopped_by(self) -> Violation | None:
        """The first violation, which is the control that stops the request."""
        return self.violations[0] if self.violations else None
```

- `class Control(Enum):` is an enumeration with four members, one per control. Each has a name (`Control.ORG_POLICY`) and a **value**, a text (`"org_policy"`). The values are what the scenario file and the printed output use.
- `PerimeterMode` has two members, `DRY_RUN` (`"dry-run"`) and `ENFORCED` (`"enforced"`). The command-line option `--mode` takes these texts.
- `Violation` is a frozen dataclass of three texts: which control objects, the constraint or permission or reason code (`detail`), and the message the real service would show.
- `Decision` has two fields, both tuples that default to the empty tuple `()`. `violations` are refusals; `logged_only` are dry-run entries that were recorded but did not block. A tuple is used instead of a list because dataclass defaults must not be shared mutable values.
- `@property def allowed(self) -> bool: return not self.violations` is true when the tuple is empty. `not` turns an empty (false-like) tuple into `True`.
- `stopped_by` returns the first violation or `None`. `self.violations[0] if self.violations else None` is a conditional expression: if the tuple has items take the first, otherwise `None`.

### `domain/requests.py`: the five things someone can ask for

`src/landing_zone/domain/requests.py`

```python
"""The requests the lesson makes, as immutable values the decision rules can evaluate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateServiceAccountKey:
    """Download a key for a service account in `project`."""

    project: str


@dataclass(frozen=True, slots=True)
class CreateBucket:
    """Create a bucket in `project` at `location` (`europe-west1`, `us-central1`, `EU`...)."""

    project: str
    location: str
    uniform_access: bool


@dataclass(frozen=True, slots=True)
class CreateVm:
    """Create a VM in `project`; `subnet` is a subnet of the shared VPC, `caller_groups` the groups of the caller."""

    project: str
    zone: str
    subnet: str | None
    external_ip: bool
    caller_groups: frozenset[str]


@dataclass(frozen=True, slots=True)
class CopyObject:
    """Copy an object from a bucket in `source_project` to one in `destination_project`."""

    caller_can_read: bool
    source_project: str
    destination_project: str


@dataclass(frozen=True, slots=True)
class ReadObject:
    """Read an object in `project`; `from_access_level` names the access level the caller's address matches, if any."""

    caller_can_read: bool
    project: str
    from_access_level: str | None


Request = CreateServiceAccountKey | CreateBucket | CreateVm | CopyObject | ReadObject
```

- Five frozen dataclasses, one per kind of request, each with exactly the facts the decision needs. `CreateServiceAccountKey` needs only the project. `CreateBucket` needs the project, the location and whether uniform access is on. `CreateVm` carries the subnet (or `None`), whether an external address is wanted, and the **groups of the caller** as a `frozenset` (a set that cannot change; a set is a collection with no order and no duplicates, which suits "is this group among them").
- `CopyObject` and `ReadObject` carry `caller_can_read` (does IAM allow the read) and the project names the perimeter cares about. `from_access_level: str | None` is the name of the access level the caller's address matches, or `None`.
- The last line, `Request = ... | ...`, gives a name to the union of the five types, so a function can say it accepts "any request".

### `domain/design.py`: the slice as values, and its consistency rules

`src/landing_zone/domain/design.py`

```python
"""The landing-zone slice as immutable values: folders, projects, the shared VPC and the perimeter."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from enum import Enum


class ProjectRole(Enum):
    """What a project is for."""

    DATA = "data"
    SERVICE = "service"
    HOST = "host"


@dataclass(frozen=True, slots=True)
class Project:
    """A project and the folder it sits in."""

    name: str
    folder: str
    role: ProjectRole


@dataclass(frozen=True, slots=True)
class Subnet:
    """A subnet of the shared VPC, the service project that uses it and the groups allowed to use it."""

    name: str
    cidr: ipaddress.IPv4Network
    service_project: str
    user_groups: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AccessLevel:
    """Callers from these address ranges count as inside the organization's trusted network."""

    name: str
    ip_subnetworks: tuple[ipaddress.IPv4Network, ...]


@dataclass(frozen=True, slots=True)
class Perimeter:
    """A VPC Service Controls perimeter around some projects and some services."""

    name: str
    title: str
    projects: tuple[str, ...]
    restricted_services: tuple[str, ...]
    access_levels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SensitiveData:
    """Where the data the perimeter protects lives."""

    project: str
    bucket: str
    object_name: str


@dataclass(frozen=True, slots=True)
class Design:
    """The whole slice."""

    domain: str
    folders: tuple[str, ...]
    projects: tuple[Project, ...]
    host_project: str
    network: str
    region: str
    subnets: tuple[Subnet, ...]
    perimeter: Perimeter
    access_levels: tuple[AccessLevel, ...]
    sensitive: SensitiveData

    def project(self, name: str) -> Project | None:
        """The project called `name`, or None when the design has none."""
        return next((p for p in self.projects if p.name == name), None)

    def subnet(self, name: str) -> Subnet | None:
        """The subnet called `name`, or None."""
        return next((s for s in self.subnets if s.name == name), None)


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

    for name in design.perimeter.projects:
        if design.project(name) is None:
            problems.append(f"perimeter project {name} is not a project")
    if not design.perimeter.projects:
        problems.append("the perimeter protects no project")
    if not design.perimeter.restricted_services:
        problems.append("the perimeter restricts no service")
    known_levels = {a.name for a in design.access_levels}
    for level in design.perimeter.access_levels:
        if level not in known_levels:
            problems.append(f"perimeter uses unknown access level {level}")

    if design.sensitive.project not in design.perimeter.projects:
        problems.append(f"sensitive data is in {design.sensitive.project}, which is outside the perimeter")
    return problems


def _duplicates(kind: str, names: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        if name in seen:
            out.append(f"duplicate {kind} {name}")
        seen.add(name)
    return out


def _overlaps(subnets: tuple[Subnet, ...]) -> list[str]:
    out = []
    for index, first in enumerate(subnets):
        for second in subnets[index + 1 :]:
            if first.cidr.overlaps(second.cidr):
                out.append(f"subnets {first.name} ({first.cidr}) and {second.name} ({second.cidr}) overlap")
    return out
```

- Lines 1 to 8 are the docstring and imports already explained above.
- `ProjectRole`, `Project`, `Subnet`, `AccessLevel`, `Perimeter`, `SensitiveData` are frozen dataclasses with one field per column of the design file. `Design` ties them together.
- `Design.project(name)` and `Design.subnet(name)` search a tuple with `next(generator, None)`: the generator produces matching items lazily and `next` takes the first or the default `None`. The return type `Project | None` forces callers to handle "not found".
- `validate_design` starts with `problems: list[str] = []`, a list that says its items are texts (the annotation helps `mypy`). The four `_duplicates` calls check folder, project, subnet and access-level names.
- The `for project in design.projects` loop checks the folder; the host checks follow: the named host must exist (`is None`) and must have the host role, and exactly one project may have it. `sum(1 for ... if ...)` counts matches.
- The subnet loop requires a service project with the service role and at least one user group (`not subnet.user_groups` is true for an empty tuple), then `_overlaps` compares ranges.
- The perimeter checks: every named project exists, the perimeter protects at least one project, restricts at least one service, and uses only known access levels (`known_levels` is a **set comprehension**, `{a.name for a in ...}`, built for fast membership tests).
- The last rule: the sensitive data's project must be one of the perimeter's projects.
- `_duplicates(kind, names)` keeps a set `seen` of names met so far; a name met a second time produces a message. `names: list[str] | tuple[str, ...]` accepts either container.
- `_overlaps` was explained in `ipaddress-and-cidr.md`.

### `domain/policy.py`: one organization policy that cannot be incomplete

The whole file was quoted and explained above (section "A value that validates itself"); its enum `PolicyKind` has the two members `BOOLEAN` and `LIST`.

### `domain/landscape.py`: the decision rules

`src/landing_zone/domain/landscape.py`

```python
"""The decision rules: a design, its policies and a perimeter mode answer who would stop a request."""

from __future__ import annotations

from collections.abc import Iterable

from landing_zone.domain.decision import Control, Decision, PerimeterMode, Violation
from landing_zone.domain.design import Design, Project
from landing_zone.domain.policy import OrgPolicy
from landing_zone.domain.requests import (
    CopyObject,
    CreateBucket,
    CreateServiceAccountKey,
    CreateVm,
    ReadObject,
    Request,
)

_STORAGE = "storage.googleapis.com"
_EU_LOCATION_GROUP = "in:eu-locations"


class Landscape:
    """Evaluate requests against one design, one set of policies and one perimeter mode."""

    def __init__(self, design: Design, policies: Iterable[OrgPolicy], perimeter_mode: PerimeterMode) -> None:
        """Create the landscape; nothing is checked here, see `application.check` for the consistency rules."""
        self._design = design
        self._policies = tuple(policies)
        self._mode = perimeter_mode

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

    def _policy(self, constraint: str, project: Project | None) -> OrgPolicy | None:
        for policy in self._policies:
            if policy.constraint == constraint and (project is None or policy.applies_to_folder(project.folder)):
                return policy
        return None

    def _key(self, request: CreateServiceAccountKey) -> Decision:
        policy = self._policy("iam.disableServiceAccountKeyCreation", self._design.project(request.project))
        if policy is not None and policy.enforce:
            return _refused(
                Control.ORG_POLICY,
                policy.constraint,
                "FAILED_PRECONDITION: Key creation is not allowed on this service account.",
            )
        return Decision()

    def _bucket(self, request: CreateBucket) -> Decision:
        project = self._design.project(request.project)
        locations = self._policy("gcp.resourceLocations", project)
        if locations is not None and not _location_allowed(request.location, locations.allowed_values):
            return _refused(
                Control.ORG_POLICY,
                locations.constraint,
                f"Constraint constraints/gcp.resourceLocations violated for [projects/{request.project}] "
                f"attempting to create a bucket in {request.location}.",
            )
        uniform = self._policy("storage.uniformBucketLevelAccess", project)
        if uniform is not None and uniform.enforce and not request.uniform_access:
            return _refused(
                Control.ORG_POLICY,
                uniform.constraint,
                f"Constraint constraints/storage.uniformBucketLevelAccess violated for [projects/{request.project}].",
            )
        return Decision()

    def _vm(self, request: CreateVm) -> Decision:
        project = self._design.project(request.project)
        external = self._policy("compute.vmExternalIpAccess", project)
        if request.external_ip and external is not None and external.deny_all:
            return _refused(
                Control.ORG_POLICY,
                external.constraint,
                f"Constraint constraints/compute.vmExternalIpAccess violated for project {request.project}.",
            )
        if request.subnet is not None:
            subnet = self._design.subnet(request.subnet)
            if subnet is not None and not (set(subnet.user_groups) & request.caller_groups):
                return _refused(
                    Control.SHARED_VPC_IAM,
                    "compute.subnetworks.use",
                    f"Required 'compute.subnetworks.use' permission for 'projects/{self._design.host_project}/regions/"
                    f"{self._design.region}/subnetworks/{subnet.name}'",
                )
        return Decision()

    def _copy(self, request: CopyObject) -> Decision:
        if not request.caller_can_read:
            return _refused(Control.IAM, "storage.objects.get", "the caller holds no role that allows the read")
        if self._in_perimeter(request.source_project) and not self._in_perimeter(request.destination_project):
            return self._perimeter(
                Violation(
                    Control.VPC_SERVICE_CONTROLS,
                    "RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER",
                    "Request is prohibited by organization's policy: the destination is outside the perimeter.",
                )
            )
        return Decision()

    def _read(self, request: ReadObject) -> Decision:
        if not request.caller_can_read:
            return _refused(Control.IAM, "storage.objects.get", "the caller holds no role that allows the read")
        trusted = set(self._design.perimeter.access_levels)
        if self._in_perimeter(request.project) and request.from_access_level not in trusted:
            return self._perimeter(
                Violation(
                    Control.VPC_SERVICE_CONTROLS,
                    "NO_MATCHING_ACCESS_LEVEL",
                    "Request is prohibited by organization's policy: the caller matches no access level "
                    "of the perimeter.",
                )
            )
        return Decision()

    def _in_perimeter(self, project: str) -> bool:
        perimeter = self._design.perimeter
        return project in perimeter.projects and _STORAGE in perimeter.restricted_services

    def _perimeter(self, violation: Violation) -> Decision:
        if self._mode is PerimeterMode.ENFORCED:
            return Decision(violations=(violation,))
        return Decision(logged_only=(violation,))


def _refused(control: Control, detail: str, message: str) -> Decision:
    return Decision(violations=(Violation(control, detail, message),))


def _location_allowed(location: str, allowed_values: tuple[str, ...]) -> bool:
    lowered = location.lower()
    for value in allowed_values:
        if value == _EU_LOCATION_GROUP and (lowered == "eu" or lowered.startswith("europe-")):
            return True
        if value.lower() == lowered:
            return True
    return False
```

- `from collections.abc import Iterable` imports a type that means "anything you can loop over". The constructor accepts any such collection of policies and stores it as a tuple.
- `_STORAGE` and `_EU_LOCATION_GROUP` are module-level **constants** (names in capitals by convention) so the text is written once.
- `class Landscape` holds `self._design`, `self._policies` and `self._mode`. The leading underscore marks them as internal. `__init__` is the constructor, run when you write `Landscape(design, policies, mode)`.
- `evaluate` is the only public method: it uses `match` to pick one private method per request class.
- `_policy(constraint, project)` finds the first policy for that constraint that applies to the project's folder. `project is None or policy.applies_to_folder(project.folder)` means: for an unknown project, accept any policy; otherwise only those that reach its folder.
- `_key`: if the policy exists and `policy.enforce` is true, return a refusal naming the organization policy with the exact message text the service gives; otherwise `Decision()`, an empty decision (allowed).
- `_bucket`: first the location rule, then the uniform-access rule. The two long messages are built from adjacent string literals: Python joins `"a" "b"` written one after the other into `"ab"`, which keeps lines short.
- `_vm` and `_copy` and `_read` and `_perimeter` and `_in_perimeter` were explained in `compute-engine.md`, `vpc-service-controls.md` and `shared-vpc-and-networking.md`.
- `_refused(control, detail, message)` is a small helper that builds a decision with one violation; it is outside the class because it uses no state.
- `_location_allowed` was explained above.

### `application/check.py`: the design and the policies, checked together

`src/landing_zone/application/check.py`

```python
"""Consistency checks over the design and the policies together."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from landing_zone.domain.design import Design, validate_design
from landing_zone.domain.policy import OrgPolicy

REQUIRED_CONSTRAINTS = (
    "iam.disableServiceAccountKeyCreation",
    "gcp.resourceLocations",
    "storage.uniformBucketLevelAccess",
    "compute.vmExternalIpAccess",
)


def check(design: Design, policies: Sequence[OrgPolicy]) -> list[str]:
    """Every problem found, design first. The policy type already enforces a reason and a blocked request."""
    problems = validate_design(design)
    counts = Counter((p.constraint, p.level) for p in policies)
    problems += [f"policy {constraint} is set twice at {level}" for (constraint, level), n in counts.items() if n > 1]
    for policy in policies:
        if policy.folder is not None and policy.folder not in design.folders:
            problems.append(f"policy {policy.constraint} is set on unknown folder {policy.folder}")
    present = {p.constraint for p in policies}
    problems += [
        f"the lesson's policy {constraint} is missing"
        for constraint in REQUIRED_CONSTRAINTS
        if constraint not in present
    ]
    return problems
```

- `Counter` (from `collections`) counts how many times each item appears. Here the items are pairs `(constraint, level)`, so a pair that appears twice means the same constraint was set twice at the same place.
- `REQUIRED_CONSTRAINTS` lists the four policies the lesson asks for.
- `problems = validate_design(design)` starts with the design's own problems; the policy checks follow in a stable order: duplicates, policies on unknown folders, missing lesson policies.
- `for (constraint, level), n in counts.items() if n > 1` unpacks each dictionary entry (a key that is itself a pair, and its count) and keeps only counts above one. `problems += [ ... ]` appends the list of messages.
- `present = {p.constraint for p in policies}` is a set of the constraints that exist; each required constraint not in it is reported.

### `application/render.py`: a policy as a document, and a table for people

`src/landing_zone/application/render.py`

```python
"""Turn policies into the documents `gcloud org-policies set-policy` takes, and into a table people can read."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from landing_zone.domain.policy import OrgPolicy, PolicyKind


def render_policy_document(
    policy: OrgPolicy, organization_id: str, *, dry_run: bool, folder_ids: dict[str, str] | None = None
) -> dict[str, Any]:
    """One policy as the dict behind the gcloud YAML; `dry_run` writes `dryRunSpec` so the policy only logs."""
    parent = f"organizations/{organization_id}"
    if policy.folder is not None:
        folder_id = (folder_ids or {}).get(policy.folder)
        if folder_id is None:
            raise KeyError(f"no folder id for {policy.folder}: pass it with --folder NAME=ID")
        parent = f"folders/{folder_id}"
    if policy.kind is PolicyKind.BOOLEAN:
        rule: dict[str, Any] = {"enforce": policy.enforce}
    elif policy.deny_all:
        rule = {"denyAll": True}
    else:
        rule = {"values": {"allowedValues": list(policy.allowed_values)}}
    return {"name": f"{parent}/policies/{policy.constraint}", "dryRunSpec" if dry_run else "spec": {"rules": [rule]}}


def explain(policies: Sequence[OrgPolicy]) -> str:
    """A Markdown table of constraint, level, reason and the request each policy blocks (step 1's Done when)."""
    lines = ["| Constraint | Level | Reason | A request it blocks | Instead |", "| --- | --- | --- | --- | --- |"]
    for policy in policies:
        cells = (f"`{policy.constraint}`", policy.level, policy.reason, policy.blocked_request, policy.instead)
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
    return "\n".join(lines) + "\n"
```

- `render_policy_document(policy, organization_id, *, dry_run, folder_ids=None)`: the bare `*` makes everything after it **keyword-only**, so a caller must write `dry_run=True`. A bare `True` in a call would be unreadable.
- `parent = f"organizations/{organization_id}"` is the default; for a folder policy `(folder_ids or {}).get(policy.folder)` looks the id up (an empty dictionary stands in when `folder_ids` is `None`) and a missing id raises `KeyError` with a message that says what to pass.
- The `if/elif/else` builds the rule from the policy kind: boolean `{"enforce": ...}`, deny-all `{"denyAll": True}`, otherwise an allow list.
- `"dryRunSpec" if dry_run else "spec"` is a conditional expression used as a **dictionary key**: the same document with one different word.
- `explain` builds a Markdown table. A **Markdown table** is text with `|` between cells and a line of `---` under the header. Each cell has `|` replaced by `\|` so a bar inside a sentence cannot break the table. `"\n".join(lines) + "\n"` glues the lines with line breaks.

### `application/scenarios.py`: the lesson's requests and their promised answers

`src/landing_zone/application/scenarios.py`

```python
"""Run the lesson's requests against a landscape and compare each answer with the one the design promises."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from landing_zone.domain.decision import Control, Decision
from landing_zone.domain.landscape import Landscape
from landing_zone.domain.requests import Request


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
class Scenario:
    """A named request with its expected answer."""

    name: str
    request: Request
    expect: Expectation


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """One scenario after it ran."""

    scenario: Scenario
    decision: Decision
    ok: bool


def run_scenarios(landscape: Landscape, scenarios: Sequence[Scenario]) -> list[ScenarioResult]:
    """Evaluate every scenario. In dry-run mode a perimeter refusal appears as a log entry, not a refusal."""
    results = []
    for scenario in scenarios:
        decision = landscape.evaluate(scenario.request)
        results.append(ScenarioResult(scenario, decision, scenario.expect.matches(decision, also_logged=True)))
    return results


def format_results(results: Sequence[ScenarioResult]) -> str:
    """One line per scenario: verdict, answer, and which control gave it."""
    lines = []
    for result in results:
        decision = result.decision
        if decision.stopped_by is not None:
            answer = f"REFUSED by {decision.stopped_by.control.value} ({decision.stopped_by.detail})"
        elif decision.logged_only:
            answer = f"allowed, but dry run would block: {decision.logged_only[0].detail}"
        else:
            answer = "allowed"
        lines.append(f"{'ok  ' if result.ok else 'FAIL'}  {result.scenario.name}: {answer}")
    return "\n".join(lines) + "\n"
```

- `Expectation.matches` was explained above. `allowed` true means the decision must have no violation; otherwise the shown violation must come from the expected control and, if a detail was given, have that detail.
- `Scenario` ties a name, a request and an expectation. `ScenarioResult` adds the decision and whether it matched (`ok`).
- `run_scenarios` loops over the scenarios, evaluates each and compares. `also_logged=True` lets a dry-run log entry stand in for the control, so in dry-run mode the perimeter scenarios still pass.
- `format_results` makes one line per result. It chooses the wording from the decision: refused (`REFUSED by control (detail)`), allowed but logged (`allowed, but dry run would block: ...`) or `allowed`. `'ok  ' if result.ok else 'FAIL'` picks the label. `.value` reads the enum's text.

### `infrastructure/yaml_files.py`: the only file that touches the disk for the model

`src/landing_zone/infrastructure/yaml_files.py`

```python
"""Adapter: read the design, the policies and the scenarios from YAML files; write policy documents."""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from landing_zone.application.scenarios import Expectation, Scenario
from landing_zone.domain.decision import Control
from landing_zone.domain.design import AccessLevel, Design, Perimeter, Project, ProjectRole, SensitiveData, Subnet
from landing_zone.domain.errors import InvalidDesign, InvalidPolicy, InvalidRequest
from landing_zone.domain.policy import OrgPolicy, PolicyKind
from landing_zone.domain.requests import (
    CopyObject,
    CreateBucket,
    CreateServiceAccountKey,
    CreateVm,
    ReadObject,
    Request,
)


def load_design(path: Path) -> Design:
    """Parse `landing-zone.yaml`; raises `InvalidDesign` for a missing key or a malformed value."""
    data = _load(path)
    try:
        vpc = data["shared_vpc"]
        perimeter = data["perimeter"]
        sensitive = data["sensitive_data"]
        return Design(
            domain=str(data["organization"]["domain"]),
            folders=tuple(str(f["name"]) for f in data["folders"]),
            projects=tuple(Project(str(p["name"]), str(p["folder"]), ProjectRole(p["role"])) for p in data["projects"]),
            host_project=str(vpc["host_project"]),
            network=str(vpc["network"]),
            region=str(vpc["region"]),
            subnets=tuple(
                Subnet(
                    str(s["name"]),
                    ipaddress.IPv4Network(s["cidr"]),
                    str(s["service_project"]),
                    tuple(str(g) for g in s.get("user_groups", [])),
                )
                for s in vpc["subnets"]
            ),
            perimeter=Perimeter(
                str(perimeter["name"]),
                str(perimeter["title"]),
                tuple(str(p) for p in perimeter["projects"]),
                tuple(str(s) for s in perimeter["restricted_services"]),
                tuple(str(a) for a in perimeter.get("access_levels", [])),
            ),
            access_levels=tuple(
                AccessLevel(str(a["name"]), tuple(ipaddress.IPv4Network(n) for n in a["ip_subnetworks"]))
                for a in data.get("access_levels", [])
            ),
            sensitive=SensitiveData(str(sensitive["project"]), str(sensitive["bucket"]), str(sensitive["object"])),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidDesign(f"{path}: {type(error).__name__}: {error}") from error


def load_policies(path: Path) -> tuple[OrgPolicy, ...]:
    """Parse `org-policies.yaml`; `InvalidPolicy` says which entry is wrong and why."""
    data = _load(path)
    try:
        return tuple(_policy(entry) for entry in data["policies"])
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidPolicy(f"{path}: {type(error).__name__}: {error}") from error


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
        deny_all=bool(entry.get("deny_all", False)),
    )


def load_scenarios(path: Path) -> tuple[Scenario, ...]:
    """Parse `scenarios.yaml`; `InvalidRequest` names the scenario that cannot be understood."""
    data = _load(path)
    scenarios = []
    for entry in data.get("scenarios", []):
        name = str(entry.get("name", "?"))
        try:
            expect = entry["expect"]
            control = Control(expect["control"]) if "control" in expect else None
            expectation = Expectation(bool(expect["allowed"]), control, expect.get("detail"))
            scenarios.append(Scenario(name, _request(entry["request"]), expectation))
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidRequest(f"scenario {name!r}: {type(error).__name__}: {error}") from error
    return tuple(scenarios)


def _request(raw: Mapping[str, Any]) -> Request:
    kind = raw["type"]
    if kind == "create_service_account_key":
        return CreateServiceAccountKey(str(raw["project"]))
    if kind == "create_bucket":
        return CreateBucket(str(raw["project"]), str(raw["location"]), bool(raw["uniform_access"]))
    if kind == "create_vm":
        subnet = raw.get("subnet")
        return CreateVm(
            str(raw["project"]),
            str(raw["zone"]),
            None if subnet is None else str(subnet),
            bool(raw["external_ip"]),
            frozenset(str(g) for g in raw.get("caller_groups", [])),
        )
    if kind == "copy_object":
        return CopyObject(bool(raw["caller_can_read"]), str(raw["source_project"]), str(raw["destination_project"]))
    if kind == "read_object":
        level = raw.get("from_access_level")
        return ReadObject(bool(raw["caller_can_read"]), str(raw["project"]), None if level is None else str(level))
    raise ValueError(f"unknown request type {kind!r}")


def write_policy_documents(directory: Path, documents: Sequence[tuple[str, Mapping[str, Any]]]) -> list[Path]:
    """Write each (file stem, document) as `<stem>.yaml` under `directory`, creating it; returns the paths."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for stem, document in documents:
        path = directory / f"{stem}.yaml"
        path.write_text(yaml.safe_dump(dict(document), sort_keys=False), encoding="utf-8")
        paths.append(path)
    return paths


def _load(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise InvalidDesign(f"{path}: not valid YAML: {error}") from error
    if not isinstance(data, dict):
        raise InvalidDesign(f"{path}: expected a mapping at the top level")
    return data
```

- `load_design` reads the file once with `_load`, then builds the immutable values. A single `try` surrounds all the indexing: `KeyError` (a missing key), `TypeError` (a value of the wrong type, for instance a number where a list was expected) and `ValueError` (a bad enum value or a bad address) all become `InvalidDesign` with the file name and the original error text. `raise ... from error` keeps the original attached so a debugger can show both.
- `str(...)` wraps every text so a number typed in YAML (`1`) cannot slip in as a number.
- `s.get("user_groups", [])` returns an empty list when the key is absent.
- `load_policies` calls `_policy` for each entry; `_policy` reads `entry["blocks"]` first (a mapping with `request` and `instead`).
- `load_scenarios` loops with `data.get("scenarios", [])`. It builds `Control(expect["control"]) if "control" in expect else None`: only refusals name a control. A bad entry is reported with its name (`name = str(entry.get("name", "?"))`).
- `_request` chooses the class from the `type` text with a chain of `if kind == ...`; the last line raises `ValueError` for an unknown type, which `load_scenarios` converts.
- In the `create_vm` branch, `None if subnet is None else str(subnet)` keeps a missing subnet as `None`; `frozenset(str(g) for g in raw.get("caller_groups", []))` turns a list of groups into a frozen set.

### `interfaces/cli.py`: the command

The whole file was quoted piece by piece in `argparse.md`. Its remaining lines:

`src/landing_zone/interfaces/cli.py`

```python
def _check(args: argparse.Namespace) -> int:
    problems = check(load_design(args.design), load_policies(args.policies))
    for problem in problems:
        print(f"problem: {problem}")
    if not problems:
        print("ok: the design and the policies are consistent")
    return 1 if problems else 0


def _explain(args: argparse.Namespace) -> int:
    print(explain(load_policies(args.policies)), end="")
    return 0


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


def _simulate(args: argparse.Namespace) -> int:
    landscape = Landscape(load_design(args.design), load_policies(args.policies), PerimeterMode(args.mode))
    results = run_scenarios(landscape, load_scenarios(args.scenarios))
    print(format_results(results), end="")
    return 0 if all(result.ok for result in results) else 1
```

- `_check` prints `problem: ...` for each problem or the single `ok:` line, and returns `1` (some problem) or `0`. `print(..., end="")` in `_explain` and `_simulate` avoids a second blank line, because the text already ends with a line break.
- `_simulate` builds the `Landscape` from the three files and the chosen mode, runs the scenarios and returns `0` only if `all(result.ok for result in results)`.
- The last lines of the file are:

`src/landing_zone/interfaces/cli.py`

```python
if __name__ == "__main__":
    raise SystemExit(main())
```

`__name__` is `"__main__"` only when the file is run directly (`python -m landing_zone.interfaces.cli`). `SystemExit(main())` ends the program with the number `main` returned as its **exit status**. The installed `landing-zone` command calls `main` through the entry point instead.

The whole file, in one piece:

`src/landing_zone/interfaces/cli.py`

```python
"""The `landing-zone` command: check the design, explain the policies, render them for gcloud, simulate requests."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from landing_zone.application.check import check
from landing_zone.application.render import explain, render_policy_document
from landing_zone.application.scenarios import format_results, run_scenarios
from landing_zone.domain.decision import PerimeterMode
from landing_zone.domain.errors import DomainError
from landing_zone.domain.landscape import Landscape
from landing_zone.infrastructure.yaml_files import (
    load_design,
    load_policies,
    load_scenarios,
    write_policy_documents,
)

DESIGN = Path("design/landing-zone.yaml")
POLICIES = Path("policies/org-policies.yaml")
SCENARIOS = Path("design/scenarios.yaml")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command; returns the exit status (0 ok, 1 a check or scenario failed, 2 unreadable input)."""
    args = _parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (DomainError, OSError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


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


def _check(args: argparse.Namespace) -> int:
    problems = check(load_design(args.design), load_policies(args.policies))
    for problem in problems:
        print(f"problem: {problem}")
    if not problems:
        print("ok: the design and the policies are consistent")
    return 1 if problems else 0


def _explain(args: argparse.Namespace) -> int:
    print(explain(load_policies(args.policies)), end="")
    return 0


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


def _simulate(args: argparse.Namespace) -> int:
    landscape = Landscape(load_design(args.design), load_policies(args.policies), PerimeterMode(args.mode))
    results = run_scenarios(landscape, load_scenarios(args.scenarios))
    print(format_results(results), end="")
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- The imports at the top bring in each layer's pieces; the constants `DESIGN`, `POLICIES`, `SCENARIOS` are the default file paths (`Path("design/landing-zone.yaml")` is relative to where you run the command). `from __future__ import annotations` was explained at the top of this note.
- `main(argv=None)` parses, calls the chosen handler and turns errors into exit status 2; `-> int` says it returns a number.
- `_parser` builds the argument parser (see `argparse.md`); each `_check`, `_explain`, `_render`, `_simulate` is a **handler**: it receives the parsed `args` and returns the exit status.

### `tests/conftest.py`: shared building blocks for the tests

`tests/conftest.py`

```python
"""Shared fixtures: the repository's real design and policies, loaded once, plus builders for small variations."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from landing_zone.domain.design import Design
from landing_zone.domain.policy import OrgPolicy
from landing_zone.infrastructure.yaml_files import load_design, load_policies

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def design() -> Design:
    return load_design(ROOT / "design/landing-zone.yaml")


@pytest.fixture(scope="session")
def policies() -> tuple[OrgPolicy, ...]:
    return load_policies(ROOT / "policies/org-policies.yaml")


@pytest.fixture
def without(design):
    """A copy of the design with some fields replaced."""

    def build(**changes):
        return replace(design, **changes)

    return build
```

- `ROOT = Path(__file__).resolve().parents[1]`: `__file__` is this file's path; `.resolve()` makes it absolute; `.parents[1]` is two folders up, the repository root.
- `@pytest.fixture(scope="session")` marks a function whose return value pytest hands to any test that names it as an argument. `scope="session"` builds it once for the whole run. `design` and `policies` load the repository's real files.
- `without` returns a **function** (`build`) that makes a copy of the design with some fields replaced (`dataclasses.replace`); a function defined inside another is a **closure**. Tests use `without(projects=...)` to make a broken variation.

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
