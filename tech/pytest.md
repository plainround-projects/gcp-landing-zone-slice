# pytest (and coverage)

## 1. What it is

pytest is a Python **test runner**. A **test** is a small function that calls your code and checks the result; if a check fails, the test fails. pytest finds files named `test_*.py`, runs every function whose name starts with `test_`, and prints a summary. A plain `assert` statement is the check. **Coverage** measures which lines of your code the tests actually ran; the `pytest-cov` plug-in adds it to pytest. Versions are pinned in `requirements-dev.lock`.

## 2. Why this repository uses it

Tests are how the repository proves its rules without a cloud account: the validation rules, the error handling and the wiring all run in a few seconds. The README's "Done when" table points at them.

## 3. Where it appears

| Path | What it does with pytest |
| --- | --- |
| `tests/unit/` | Fast tests with no network: domain, application (with fakes), adapters, web or command-line layers, and checks on the infrastructure files. |
| `tests/e2e/` | The program as a user runs it: a subprocess over the repository's own design files (marker `e2e`; no Docker and no cloud account needed). |
| `tests/conftest.py` | Shared **fixtures** (setup helpers) used by many tests. |
| `pyproject.toml` | `[tool.pytest.ini_options]` and `[tool.coverage.*]`. |
| `Makefile` | `make test-python` runs unit tests with coverage and fails below 95% on the domain and application layers. |
| `.github/workflows/ci.yml` | Runs the same make target on every push. |

## 4. How it works underneath

pytest imports each test file, collects the test functions, and calls them one by one. When it sees `assert a == b` it rewrites the assertion at import time so that a failure shows both values. A **fixture** is a function marked `@pytest.fixture`; a test that lists its name as a parameter receives its return value. `@pytest.mark.parametrize("x", [1, 2, 3])` runs one test function once per value. **Markers** are labels such as `e2e` that let you select tests (`-m e2e`). `monkeypatch` and `caplog` are built-in fixtures: the first changes environment variables or attributes for one test and undoes the change; the second captures log records.

Coverage works by watching which lines run. With `branch = true` it also notes whether each `if` took both ways.

## 5. Walkthrough of this repository's use

`pyproject.toml`

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
markers = [
    "e2e: runs the command-line program as a subprocess against the repository's own design files",
]
```

- `testpaths = ["tests"]`: where to look when you run plain `pytest`.
- `addopts = "-ra --strict-markers"`: `-ra` prints a summary of everything that was not a plain pass; `--strict-markers` turns an unknown marker (a typo) into an error.
- `markers = [...]` declares the allowed markers and explains them.

`pyproject.toml`

```toml
[tool.coverage.run]
source = ["landing_zone"]
branch = true

[tool.coverage.report]
show_missing = true

[tool.importlinter]
```

- `source = ["landing_zone"]` limits measuring to this package.
- `branch = true` measures branches as well as lines.
- `show_missing = true` lists the line numbers that no test reached.

The make target:

`Makefile`

```make
test-python: $(STAMP)
	$(PY) -m pytest tests/unit --cov=landing_zone --cov-report=term
	$(PY) -m coverage report --include='src/landing_zone/domain/*,src/landing_zone/application/*' --fail-under=95
```

`--cov=landing_zone --cov-report=term` prints a coverage table; the second command (`coverage report ... --fail-under=95`) fails the build if the domain and application layers drop below 95%, which keeps the core fully tested.

### An example test

`tests/unit/domain/test_landscape.py`

```python
def test_a_team_can_use_its_own_subnet_and_not_the_others(enforced):
    own = enforced.evaluate(CreateVm("prod-app", "europe-west1-b", "subnet-prod", False, PROD))
    other = enforced.evaluate(CreateVm("prod-app", "europe-west1-b", "subnet-dev", False, PROD))
    assert own.allowed
    assert (other.stopped_by.control, other.stopped_by.detail) == (Control.SHARED_VPC_IAM, "compute.subnetworks.use")
    assert "subnet-dev" in other.stopped_by.message
```

The `enforced` argument is a **fixture** (see `conftest.py` and the top of the file): a `Landscape` built from the repository's real design and policies with the perimeter enforced. The test asks the same question twice, once for the team's own subnet and once for the other team's, and checks which control answers. It needs no organization and no network, and its name states the rule it protects.

## Every test file, and what each test proves

The basics first, as they appear in every file below.

- A **test** is a function whose name starts with `test_`. pytest finds it, calls it, and reports a pass if it returns normally and a failure if it raises an exception.
- `assert expression` raises `AssertionError` when the expression is false. pytest rewrites asserts so the failure message shows both sides of a comparison.
- A **fixture** is a helper function marked `@pytest.fixture`. When a test lists a fixture's name as a parameter, pytest calls the fixture and passes its result in. The fixtures `design`, `policies` and `without` come from `tests/conftest.py` (explained in `python.md`); `enforced` and `dry_run` are defined at the top of `test_landscape.py`.
- `@pytest.mark.parametrize` runs one test function several times with different inputs, each run reported separately.
- `with pytest.raises(SomeError, match="text"):` passes only if the code inside raises that exception and its message contains `text` (a regular expression, see `regular-expressions.md`).
- `tmp_path` is a built-in fixture: a new empty folder (a `Path`) for this test only, deleted later. `capsys` is a built-in fixture that captures what the program prints to the screen (standard output and standard error) so the test can read it.
- The pattern `design.project("nope") is None` uses `is` because `None` is a single object.

### `tests/unit/domain/test_decision.py`

`tests/unit/domain/test_decision.py`

```python
from landing_zone.domain.decision import Control, Decision, Violation


def test_a_decision_with_no_violation_is_allowed_and_names_no_control():
    decision = Decision()
    assert decision.allowed
    assert decision.stopped_by is None


def test_the_first_violation_is_the_control_that_stops_the_request():
    first = Violation(Control.IAM, "storage.objects.get", "no role")
    second = Violation(Control.ORG_POLICY, "x", "y")
    decision = Decision(violations=(first, second))
    assert not decision.allowed
    assert decision.stopped_by is first


def test_logged_only_violations_do_not_block():
    assert Decision(logged_only=(Violation(Control.VPC_SERVICE_CONTROLS, "R", "m"),)).allowed
```

- Test one: a `Decision()` with no arguments is allowed (`allowed` true) and `stopped_by` is `None`.
- Test two: with two violations, the decision is not allowed, and `stopped_by is first` checks that it is **the same object** as the first one: the first violation is the control that stops the request.
- Test three: a decision that only has `logged_only` entries is still allowed. This is the dry-run rule in one line.

### `tests/unit/domain/test_policy.py`

`tests/unit/domain/test_policy.py`

```python
import pytest

from landing_zone.domain.errors import InvalidPolicy
from landing_zone.domain.policy import OrgPolicy, PolicyKind


def policy(**overrides):
    values = {
        "constraint": "iam.disableServiceAccountKeyCreation",
        "kind": PolicyKind.BOOLEAN,
        "level": "organization",
        "reason": "no downloadable keys",
        "blocked_request": "a key for a laptop script",
        "instead": "impersonate",
        "enforce": True,
    }
    return OrgPolicy(**{**values, **overrides})


def test_the_repositorys_policies_each_have_a_reason_and_a_blocked_request(policies):
    assert len(policies) == 4
    assert all(p.reason and p.blocked_request and p.instead for p in policies)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"constraint": ""}, "not a constraint name"),
        ({"constraint": "a/b"}, "not a constraint name"),
        ({"reason": "  "}, "no reason"),
        ({"blocked_request": ""}, "blocks"),
        ({"instead": ""}, "blocks"),
        ({"level": "project:x"}, "level must be"),
        ({"allowed_values": ("x",)}, "boolean constraint takes only enforce"),
        ({"deny_all": True}, "boolean constraint takes only enforce"),
        ({"kind": PolicyKind.LIST, "enforce": True, "allowed_values": ("x",)}, "not enforce"),
        ({"kind": PolicyKind.LIST, "enforce": False}, "exactly one of"),
        ({"kind": PolicyKind.LIST, "enforce": False, "allowed_values": ("x",), "deny_all": True}, "exactly one of"),
    ],
)
def test_incomplete_or_contradictory_policies_are_rejected_with_the_constraint_named(overrides, message):
    with pytest.raises(InvalidPolicy, match=message):
        policy(**overrides)


def test_a_folder_policy_applies_only_to_its_folder_and_an_organization_policy_to_all():
    assert policy(level="folder:production").folder == "production"
    assert policy(level="folder:production").applies_to_folder("production")
    assert not policy(level="folder:production").applies_to_folder("shared")
    assert policy().folder is None
    assert policy().applies_to_folder("anything")
```

- `policy(**overrides)` is a **builder**: it holds a valid policy as a dictionary `values` and `{**values, **overrides}` merges a second dictionary over the first, so a test names only what it changes. `OrgPolicy(**dict)` calls the class with the dictionary's items as keyword arguments.
- The first test checks the repository's four policies each have a reason, a blocked request and an alternative.
- The parametrized test runs eleven times. Each pair is `(overrides, message)`: an empty or slash-containing constraint name, a blank reason, a missing blocked request or alternative, a wrong level, a boolean policy given list fields, a list policy given `enforce`, and a list policy with neither or both of `allowed_values` and `deny_all`. Each must raise `InvalidPolicy` with the matching words.
- The last test checks the folder rules: `level="folder:production"` gives `.folder == "production"`, applies to that folder only; an organization policy has no folder and applies to everything.

### `tests/unit/domain/test_design.py`

`tests/unit/domain/test_design.py`

```python
import ipaddress
from dataclasses import replace

from landing_zone.domain.design import Project, ProjectRole, Subnet, validate_design


def test_the_repositorys_design_is_consistent(design):
    assert validate_design(design) == []


def test_lookup_helpers_return_none_for_unknown_names(design):
    assert design.project("prod-data").folder == "production"
    assert design.project("nope") is None
    assert design.subnet("subnet-dev").cidr == ipaddress.ip_network("10.60.0.0/24")
    assert design.subnet("nope") is None


def test_duplicate_names_are_reported(without, design):
    problems = validate_design(without(folders=("a", "a"), projects=(*design.projects, design.projects[0])))
    assert "duplicate folder a" in problems
    assert "duplicate project prod-data" in problems


def test_a_project_in_an_unknown_folder_is_reported(without, design):
    stray = Project("stray", "nowhere", ProjectRole.SERVICE)
    assert "project stray is in unknown folder nowhere" in validate_design(without(projects=(*design.projects, stray)))


def test_overlapping_subnets_are_reported(without, design):
    first, second = design.subnets
    clash = replace(second, cidr=ipaddress.ip_network("10.50.0.128/25"))
    problems = validate_design(without(subnets=(first, clash)))
    assert any("overlap" in p for p in problems)


def test_a_subnet_without_users_or_a_service_project_is_reported(without, design):
    orphan = Subnet("subnet-x", ipaddress.IPv4Network("10.70.0.0/24"), "net-host", ())
    problems = validate_design(without(subnets=(*design.subnets, orphan)))
    assert "subnet subnet-x names net-host, which is not a service project" in problems
    assert "subnet subnet-x has no user group, so nobody may use it" in problems


def test_the_host_project_must_exist_and_be_the_only_host(without, design):
    assert any("is not a project" in p for p in validate_design(without(host_project="ghost")))
    second_host = Project("net-2", "shared", ProjectRole.HOST)
    assert "exactly one project must have role host" in validate_design(
        without(projects=(*design.projects, second_host))
    )
    wrong_role = tuple(replace(p, role=ProjectRole.SERVICE) if p.name == "net-host" else p for p in design.projects)
    assert "host project net-host must have role host" in validate_design(without(projects=wrong_role))


def test_the_perimeter_must_protect_a_known_project_with_known_levels(without, design):
    perimeter = replace(design.perimeter, projects=("ghost",), restricted_services=(), access_levels=("nobody",))
    problems = validate_design(without(perimeter=perimeter))
    assert "perimeter project ghost is not a project" in problems
    assert "perimeter uses unknown access level nobody" in problems
    assert "the perimeter restricts no service" in problems
    assert any("outside the perimeter" in p for p in problems)


def test_an_empty_perimeter_is_reported(without, design):
    assert "the perimeter protects no project" in validate_design(
        without(perimeter=replace(design.perimeter, projects=()))
    )
```

- `ipaddress.ip_network("10.60.0.0/24")` builds the same kind of range object as the loader does (see `ipaddress-and-cidr.md`).
- Test one: the real design has no problems (`validate_design(design) == []`).
- Test two: the lookup helpers return the object for a known name and `None` for an unknown one.
- Test three: `without(folders=("a", "a"), projects=(*design.projects, design.projects[0]))` makes a copy of the design with a duplicated folder and a duplicated project; `(*design.projects, x)` unpacks a tuple and adds one more item. The messages must be among the problems.
- Test four: a project in a folder that does not exist.
- Test five: `first, second = design.subnets` unpacks the two subnets; `replace(second, cidr=...)` copies the second with a clashing range. The text "overlap" must appear.
- Test six: a subnet that names the host project (not a service project) and has an empty user tuple `()` gets both messages.
- Test seven: `host_project="ghost"` gives "is not a project"; a second host gives "exactly one project must have role host"; flipping the real host to the service role gives "host project net-host must have role host".
- Test eight: a perimeter built with `projects=("ghost",)`, `restricted_services=()` and `access_levels=("nobody",)` produces four messages: the project is not a project, the access level is unknown, the perimeter restricts no service, and the sensitive data's project is outside the perimeter.
- Test nine: an empty perimeter (no projects, no services) is reported.

### `tests/unit/domain/test_landscape.py`

`tests/unit/domain/test_landscape.py`

```python
import pytest

from landing_zone.domain.decision import Control, PerimeterMode
from landing_zone.domain.landscape import Landscape
from landing_zone.domain.requests import CopyObject, CreateBucket, CreateServiceAccountKey, CreateVm, ReadObject

PROD = frozenset({"group:team-prod@example-lab.org"})
DEV = frozenset({"group:team-dev@example-lab.org"})


@pytest.fixture
def enforced(design, policies):
    return Landscape(design, policies, PerimeterMode.ENFORCED)


@pytest.fixture
def dry_run(design, policies):
    return Landscape(design, policies, PerimeterMode.DRY_RUN)


def test_a_service_account_key_is_refused_by_the_organization_policy(enforced):
    stop = enforced.evaluate(CreateServiceAccountKey("dev-app")).stopped_by
    assert (stop.control, stop.detail) == (Control.ORG_POLICY, "iam.disableServiceAccountKeyCreation")
    assert "Key creation is not allowed" in stop.message


@pytest.mark.parametrize(
    ("location", "allowed"),
    [("europe-west1", True), ("EU", True), ("europe-north1", True), ("us-central1", False), ("asia-east1", False)],
)
def test_a_bucket_must_be_in_an_eu_location(enforced, location, allowed):
    decision = enforced.evaluate(CreateBucket("dev-app", location, uniform_access=True))
    assert decision.allowed is allowed
    if not allowed:
        assert "constraints/gcp.resourceLocations violated" in decision.stopped_by.message


def test_a_bucket_with_object_acls_is_refused_even_in_the_eu(enforced):
    stop = enforced.evaluate(CreateBucket("dev-app", "europe-west1", uniform_access=False)).stopped_by
    assert stop.detail == "storage.uniformBucketLevelAccess"


def test_a_vm_with_a_public_address_is_refused_and_a_private_one_is_not(enforced):
    public = enforced.evaluate(CreateVm("dev-app", "europe-west1-b", "subnet-dev", True, DEV))
    private = enforced.evaluate(CreateVm("dev-app", "europe-west1-b", "subnet-dev", False, DEV))
    assert public.stopped_by.detail == "compute.vmExternalIpAccess"
    assert private.allowed


def test_a_team_can_use_its_own_subnet_and_not_the_others(enforced):
    own = enforced.evaluate(CreateVm("prod-app", "europe-west1-b", "subnet-prod", False, PROD))
    other = enforced.evaluate(CreateVm("prod-app", "europe-west1-b", "subnet-dev", False, PROD))
    assert own.allowed
    assert (other.stopped_by.control, other.stopped_by.detail) == (Control.SHARED_VPC_IAM, "compute.subnetworks.use")
    assert "subnet-dev" in other.stopped_by.message


def test_a_vm_with_no_shared_subnet_is_only_subject_to_the_organization_policies(enforced):
    assert enforced.evaluate(CreateVm("dev-app", "europe-west1-b", None, False, frozenset())).allowed


def test_copying_data_out_of_the_perimeter_is_refused_when_enforced_though_iam_allows_it(enforced):
    stop = enforced.evaluate(CopyObject(True, "prod-data", "outside")).stopped_by
    assert (stop.control, stop.detail) == (Control.VPC_SERVICE_CONTROLS, "RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER")


def test_the_same_copy_in_dry_run_mode_succeeds_and_is_logged(dry_run):
    decision = dry_run.evaluate(CopyObject(True, "prod-data", "outside"))
    assert decision.allowed
    assert decision.logged_only[0].detail == "RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER"


def test_copying_inside_the_perimeter_or_from_outside_it_is_not_a_violation(enforced):
    assert enforced.evaluate(CopyObject(True, "prod-data", "prod-data")).allowed
    assert enforced.evaluate(CopyObject(True, "prod-app", "outside")).allowed


def test_reading_from_outside_every_access_level_is_refused_and_from_the_office_is_not(enforced):
    outside = enforced.evaluate(ReadObject(True, "prod-data", None))
    office = enforced.evaluate(ReadObject(True, "prod-data", "office"))
    other_level = enforced.evaluate(ReadObject(True, "prod-data", "not-in-the-perimeter"))
    assert outside.stopped_by.detail == "NO_MATCHING_ACCESS_LEVEL"
    assert other_level.stopped_by.detail == "NO_MATCHING_ACCESS_LEVEL"
    assert office.allowed


def test_a_read_in_a_project_outside_the_perimeter_is_not_affected_by_it(enforced):
    assert enforced.evaluate(ReadObject(True, "prod-app", None)).allowed


def test_iam_answers_first_so_a_caller_without_a_read_role_learns_nothing_about_the_perimeter(enforced):
    for request in (CopyObject(False, "prod-data", "outside"), ReadObject(False, "prod-data", None)):
        stop = enforced.evaluate(request).stopped_by
        assert (stop.control, stop.detail) == (Control.IAM, "storage.objects.get")


def test_without_the_policies_nothing_blocks_key_creation_or_regions(design):
    open_landscape = Landscape(design, (), PerimeterMode.ENFORCED)
    assert open_landscape.evaluate(CreateServiceAccountKey("dev-app")).allowed
    assert open_landscape.evaluate(CreateBucket("dev-app", "us-central1", uniform_access=False)).allowed
    assert open_landscape.evaluate(CreateVm("dev-app", "z", None, True, frozenset())).allowed


def test_a_folder_policy_binds_only_projects_in_that_folder(design, policies):
    import dataclasses

    scoped = tuple(
        dataclasses.replace(p, level="folder:production")
        if p.constraint == "iam.disableServiceAccountKeyCreation"
        else p
        for p in policies
    )
    landscape = Landscape(design, scoped, PerimeterMode.ENFORCED)
    assert not landscape.evaluate(CreateServiceAccountKey("prod-app")).allowed
    assert landscape.evaluate(CreateServiceAccountKey("dev-app")).allowed


def test_a_perimeter_that_does_not_restrict_storage_does_not_stop_a_copy(design, policies):
    import dataclasses

    only_bigquery = dataclasses.replace(design.perimeter, restricted_services=("bigquery.googleapis.com",))
    landscape = Landscape(dataclasses.replace(design, perimeter=only_bigquery), policies, PerimeterMode.ENFORCED)
    assert landscape.evaluate(CopyObject(True, "prod-data", "outside")).allowed
```

- Two fixtures build a `Landscape` from the real design and policies, one with the perimeter enforced, one in dry run. `PROD` and `DEV` are the caller groups of the two teams.
- The first group of tests checks the organization policies: a key is refused with the message "Key creation is not allowed"; a bucket outside the EU is refused (parametrized over five locations: `europe-west1`, `EU`, `europe-north1` allowed, `us-central1`, `asia-east1` refused); a bucket with per-object ACLs is refused even in the EU; a VM with a public address is refused and a private one is not.
- The next tests check Shared VPC: a team can use its own subnet and not the other; the refusal names `subnet-dev` and `compute.subnetworks.use`; a VM with no shared subnet (`None`) is subject only to the policies.
- Then the perimeter: a copy out is refused when enforced even though IAM allows it; the same copy in dry run is allowed and logged (`decision.logged_only[0].detail`); a copy inside the perimeter, or from a project outside it, is not a violation; a read from no access level, or from an access level the perimeter does not accept, is refused with `NO_MATCHING_ACCESS_LEVEL`, and from the office it is allowed; a read in a project outside the perimeter is unaffected.
- The IAM-first test loops over two requests whose caller cannot read (`CopyObject(False, ...)`, `ReadObject(False, ...)`) and demands the IAM refusal: a caller without a read role learns nothing about the perimeter.
- `Landscape(design, (), PerimeterMode.ENFORCED)` has no policies: nothing blocks keys, regions or public addresses. This proves the policies are what do the blocking.
- The folder-policy test uses `import dataclasses` inside the function and replaces the level of one policy with `folder:production`; the key is then refused in `prod-app` (a production project) and allowed in `dev-app`.
- The last test builds a perimeter that restricts only BigQuery. `_in_perimeter` is then false for storage, so the copy is allowed.

### `tests/unit/application/test_check_render_scenarios.py`

`tests/unit/application/test_check_render_scenarios.py`

```python
from dataclasses import replace
from pathlib import Path

import pytest

from landing_zone.application.check import check
from landing_zone.application.render import explain, render_policy_document
from landing_zone.application.scenarios import Expectation, Scenario, format_results, run_scenarios
from landing_zone.domain.decision import Control, PerimeterMode
from landing_zone.domain.landscape import Landscape
from landing_zone.domain.requests import CopyObject, CreateServiceAccountKey
from landing_zone.infrastructure.yaml_files import load_scenarios

ROOT = Path(__file__).resolve().parents[3]


def test_the_repositorys_design_and_policies_pass_every_check(design, policies):
    assert check(design, policies) == []


def test_a_missing_lesson_policy_a_duplicate_and_a_policy_on_an_unknown_folder_are_reported(design, policies):
    reduced = tuple(p for p in policies if p.constraint != "gcp.resourceLocations")
    duplicated = (*reduced, reduced[0])
    stray = replace(reduced[1], level="folder:nowhere")
    problems = check(design, (*duplicated, stray))
    assert "the lesson's policy gcp.resourceLocations is missing" in problems
    assert any("is set twice at organization" in p for p in problems)
    assert any("unknown folder nowhere" in p for p in problems)


def test_design_problems_come_first(design, policies):
    broken = replace(design, host_project="ghost")
    assert "host project ghost is not a project" in check(broken, policies)


def test_a_boolean_policy_renders_as_the_gcloud_document(policies):
    keys = next(p for p in policies if p.constraint == "iam.disableServiceAccountKeyCreation")
    assert render_policy_document(keys, "123456789012", dry_run=False) == {
        "name": "organizations/123456789012/policies/iam.disableServiceAccountKeyCreation",
        "spec": {"rules": [{"enforce": True}]},
    }


def test_list_policies_render_allowed_values_or_deny_all(policies):
    by_name = {p.constraint: p for p in policies}
    assert render_policy_document(by_name["gcp.resourceLocations"], "1", dry_run=False)["spec"] == {
        "rules": [{"values": {"allowedValues": ["in:eu-locations"]}}]
    }
    assert render_policy_document(by_name["compute.vmExternalIpAccess"], "1", dry_run=False)["spec"] == {
        "rules": [{"denyAll": True}]
    }


def test_dry_run_writes_dry_run_spec_so_the_policy_only_logs(policies):
    document = render_policy_document(policies[0], "1", dry_run=True)
    assert "dryRunSpec" in document
    assert "spec" not in document


def test_a_folder_policy_renders_under_the_folder_and_needs_its_id(policies):
    scoped = replace(policies[0], level="folder:production")
    assert render_policy_document(scoped, "1", dry_run=False, folder_ids={"production": "555"})["name"].startswith(
        "folders/555/policies/"
    )
    with pytest.raises(KeyError, match="no folder id for production"):
        render_policy_document(scoped, "1", dry_run=False)


def test_the_explanation_has_a_row_per_policy_with_reason_and_blocked_request(policies):
    table = explain(policies).splitlines()
    assert len(table) == 2 + len(policies)
    assert "public IP address" in table[-1]


def test_every_lesson_scenario_is_answered_as_promised_when_enforced(design, policies):
    scenarios = load_scenarios(ROOT / "design/scenarios.yaml")
    results = run_scenarios(Landscape(design, policies, PerimeterMode.ENFORCED), scenarios)
    assert len(results) == 13
    assert [r.scenario.name for r in results if not r.ok] == []


def test_in_dry_run_the_perimeter_scenarios_pass_through_the_log_and_do_not_block(design, policies):
    scenarios = load_scenarios(ROOT / "design/scenarios.yaml")
    results = run_scenarios(Landscape(design, policies, PerimeterMode.DRY_RUN), scenarios)
    assert all(r.ok for r in results)
    perimeter = [r for r in results if r.decision.logged_only]
    assert len(perimeter) == 2
    assert all(r.decision.allowed for r in perimeter)
    assert "dry run would block: NO_MATCHING_ACCESS_LEVEL" in format_results(perimeter)


def test_a_wrong_expectation_is_a_failed_scenario(design, policies):
    scenario = Scenario("key", CreateServiceAccountKey("dev-app"), Expectation(True))
    results = run_scenarios(Landscape(design, policies, PerimeterMode.ENFORCED), [scenario])
    assert not results[0].ok
    assert format_results(results).startswith("FAIL  key: REFUSED by org_policy")


def test_an_expectation_checks_the_control_and_the_detail(design, policies):
    landscape = Landscape(design, policies, PerimeterMode.ENFORCED)
    decision = landscape.evaluate(CopyObject(True, "prod-data", "outside"))
    assert Expectation(False, Control.VPC_SERVICE_CONTROLS).matches(decision)
    assert not Expectation(False, Control.ORG_POLICY).matches(decision)
    assert not Expectation(False, Control.VPC_SERVICE_CONTROLS, "OTHER").matches(decision)
    assert not Expectation(False, Control.VPC_SERVICE_CONTROLS).matches(
        landscape.evaluate(CopyObject(True, "prod-data", "prod-data"))
    )
```

- `ROOT = Path(__file__).resolve().parents[3]` is the repository root (this file is three folders deep).
- `check` tests: the real files pass; a reduced policy tuple (without `gcp.resourceLocations`), a duplicate (`(*reduced, reduced[0])`) and a policy moved to the unknown folder `nowhere` produce three messages; a broken design's problems come first.
- Render tests: a boolean policy renders to the exact dictionary the `gcloud` command wants; the list policies render `allowedValues` and `denyAll`; with `dry_run=True` the document contains `dryRunSpec` and not `spec`; a folder policy renders under `folders/555/policies/` and, without the id, raises `KeyError` containing "no folder id for production".
- `explain` test: the table has two header lines plus one row per policy, and the last row mentions the public address.
- Scenario tests: all 13 scenarios of `design/scenarios.yaml` pass when enforced (`[... if not r.ok] == []` lists the names of any that fail, so the failure message shows them); in dry run all pass, exactly two have `logged_only` entries, they are allowed, and the printed text says "dry run would block: NO_MATCHING_ACCESS_LEVEL".
- The last two tests prove the comparison itself works: a scenario with a wrong expectation fails and prints `FAIL  key: REFUSED by org_policy`; an `Expectation` must match the control and the detail, and "allowed" copies do not match a refusal expectation.

### `tests/unit/infrastructure/test_yaml_files.py`

`tests/unit/infrastructure/test_yaml_files.py`

```python
from pathlib import Path

import pytest
import yaml

from landing_zone.domain.errors import InvalidDesign, InvalidPolicy, InvalidRequest
from landing_zone.infrastructure.yaml_files import load_design, load_policies, load_scenarios, write_policy_documents

ROOT = Path(__file__).resolve().parents[3]


def test_the_design_file_loads_into_the_lessons_hierarchy(design):
    assert design.domain == "example-lab.org"
    assert design.folders == ("production", "non-production", "shared")
    assert [p.name for p in design.projects] == ["prod-data", "prod-app", "dev-app", "net-host"]
    assert [str(s.cidr) for s in design.subnets] == ["10.50.0.0/24", "10.60.0.0/24"]
    assert design.perimeter.projects == ("prod-data",)
    assert design.sensitive.object_name == "customers.csv"


def test_the_policy_file_loads_the_four_lesson_policies(policies):
    assert [p.constraint for p in policies] == [
        "iam.disableServiceAccountKeyCreation",
        "gcp.resourceLocations",
        "storage.uniformBucketLevelAccess",
        "compute.vmExternalIpAccess",
    ]


def test_the_scenario_file_loads_every_request_type():
    scenarios = load_scenarios(ROOT / "design/scenarios.yaml")
    assert {type(s.request).__name__ for s in scenarios} == {
        "CreateServiceAccountKey",
        "CreateBucket",
        "CreateVm",
        "CopyObject",
        "ReadObject",
    }


def write(tmp_path, text):
    path = tmp_path / "f.yaml"
    path.write_text(text)
    return path


def test_a_design_with_a_missing_key_names_the_key(tmp_path):
    with pytest.raises(InvalidDesign, match="KeyError"):
        load_design(write(tmp_path, "organization: {domain: x}\n"))


@pytest.mark.parametrize("text", ["- a\n- b\n", "key: [unclosed\n"])
def test_input_that_is_not_a_mapping_or_not_yaml_is_an_invalid_design(tmp_path, text):
    with pytest.raises(InvalidDesign):
        load_design(write(tmp_path, text))


def test_a_policy_without_a_reason_is_rejected_by_the_loader(tmp_path):
    text = (
        "policies:\n  - {constraint: x.y, kind: boolean, enforce: true, reason: '', blocks: {request: a, instead: b}}\n"
    )
    with pytest.raises(InvalidPolicy, match="no reason"):
        load_policies(write(tmp_path, text))


def test_a_policy_with_an_unknown_kind_is_rejected(tmp_path):
    text = "policies:\n  - constraint: x.y\n    kind: weird\n    reason: r\n    blocks: {request: a, instead: b}\n"
    with pytest.raises(InvalidPolicy, match="weird"):
        load_policies(write(tmp_path, text))


@pytest.mark.parametrize(
    "entry",
    [
        "{name: n, request: {type: teleport}, expect: {allowed: true}}",
        "{name: n, request: {type: create_bucket, project: p}, expect: {allowed: true}}",
        "{name: n, request: {type: create_bucket, project: p, location: l, uniform_access: true},"
        " expect: {allowed: false, control: nonsense}}",
    ],
)
def test_a_scenario_that_cannot_be_understood_is_named(tmp_path, entry):
    with pytest.raises(InvalidRequest, match="scenario 'n'"):
        load_scenarios(write(tmp_path, f"scenarios:\n  - {entry}\n"))


def test_policy_documents_are_written_as_yaml_files(tmp_path):
    paths = write_policy_documents(tmp_path / "out", [("a.b", {"name": "n", "spec": {"rules": [{"enforce": True}]}})])
    assert [p.name for p in paths] == ["a.b.yaml"]
    assert yaml.safe_load(paths[0].read_text()) == {"name": "n", "spec": {"rules": [{"enforce": True}]}}
```

- The first three tests check that the real files load into what the lesson describes: names, ranges, the four constraint names in order, and that the scenarios contain all five request types. `{type(s.request).__name__ for s in scenarios}` is a set comprehension of the class names.
- `write(tmp_path, text)` is a small helper that writes `text` to a temporary file and returns its path.
- Error tests: a design missing most keys raises `InvalidDesign` whose message contains "KeyError"; a list at the top level and a broken YAML text (`key: [unclosed`) both raise `InvalidDesign`; a policy with an empty reason, and one with the unknown kind `weird`, raise `InvalidPolicy`; three bad scenario entries (unknown type, missing keys, unknown control) raise `InvalidRequest` naming the scenario `'n'`.
- The strings with `\n` inside are YAML written on one line; `{constraint: x.y, kind: boolean}` is YAML's flow style (see `yaml.md`).
- The last test writes one policy document and reads it back with `yaml.safe_load`, comparing it with the original dictionary.

### `tests/unit/interfaces/test_cli.py`

`tests/unit/interfaces/test_cli.py`

```python
from pathlib import Path

import yaml

from landing_zone.interfaces.cli import main


def run(capsys, *argv):
    status = main(list(argv))
    captured = capsys.readouterr()
    return status, captured.out, captured.err


def test_check_passes_on_the_repositorys_files(capsys):
    assert run(capsys, "check") == (0, "ok: the design and the policies are consistent\n", "")


def test_check_fails_and_lists_problems_for_a_broken_design(capsys, tmp_path):
    design = tmp_path / "d.yaml"
    text = Path("design/landing-zone.yaml").read_text().replace("host_project: net-host", "host_project: ghost")
    design.write_text(text)
    status, out, _ = run(capsys, "--design", str(design), "check")
    assert status == 1
    assert "problem: host project ghost is not a project" in out


def test_explain_prints_the_table(capsys):
    status, out, _ = run(capsys, "explain")
    assert status == 0
    assert out.count("\n") == 6
    assert "`gcp.resourceLocations`" in out


def test_render_policies_writes_a_file_per_policy_for_the_organization(capsys, tmp_path):
    status, out, _ = run(capsys, "render-policies", "--org", "123456789012", "--out", str(tmp_path / "p"))
    assert status == 0
    assert len(out.splitlines()) == 4
    document = yaml.safe_load((tmp_path / "p" / "compute.vmExternalIpAccess.yaml").read_text())
    assert document == {
        "name": "organizations/123456789012/policies/compute.vmExternalIpAccess",
        "spec": {"rules": [{"denyAll": True}]},
    }


def test_render_policies_dry_run_writes_dry_run_spec(capsys, tmp_path):
    run(capsys, "render-policies", "--org", "1", "--out", str(tmp_path), "--dry-run")
    assert "dryRunSpec" in (tmp_path / "gcp.resourceLocations.yaml").read_text()


def test_simulate_enforced_and_dry_run_both_pass(capsys):
    for mode in ("enforced", "dry-run"):
        status, out, _ = run(capsys, "simulate", "--mode", mode)
        assert status == 0
        assert "FAIL" not in out
    assert "REFUSED by vpc_service_controls (RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER)" in run(capsys, "simulate")[1]


def test_simulate_exits_1_when_a_promise_is_broken(capsys, tmp_path):
    scenarios = tmp_path / "s.yaml"
    scenarios.write_text(
        "scenarios:\n  - name: wrong\n    request: {type: create_service_account_key, project: dev-app}\n"
        "    expect: {allowed: true}\n"
    )
    status, out, _ = run(capsys, "simulate", "--scenarios", str(scenarios))
    assert status == 1
    assert out.startswith("FAIL  wrong")


def test_a_missing_file_is_a_clean_error(capsys):
    status, _, err = run(capsys, "--design", "nope.yaml", "check")
    assert status == 2
    assert err.startswith("error:")


def test_a_folder_policy_without_its_id_is_a_clean_error(capsys, tmp_path):
    policies = tmp_path / "p.yaml"
    text = Path("policies/org-policies.yaml").read_text().replace("level: organization", "level: folder:production", 1)
    policies.write_text(text)
    status, _, err = run(
        capsys, "--policies", str(policies), "render-policies", "--org", "1", "--out", str(tmp_path / "o")
    )
    assert status == 2
    assert "no folder id for production" in err
```

- `run(capsys, *argv)` calls `main(list(argv))` directly (no new process), reads what was printed with `capsys.readouterr()` and returns `(status, out, err)`. `*argv` collects any number of arguments.
- The tests cover every subcommand: `check` on the real files prints the `ok` line and returns 0 (compared as one tuple); with a design edited by `.replace("host_project: net-host", "host_project: ghost")` it returns 1 and prints the problem; `explain` prints a table with six line breaks (two header lines and four rows); `render-policies` writes one file per policy and each is the expected dictionary; with `--dry-run` it writes `dryRunSpec`; `simulate` in both modes passes and prints no `FAIL`; a wrong promise makes `simulate` return 1 and print a line starting `FAIL  wrong`; a missing file returns 2 and an `error:` line on standard error; a folder policy without its id returns 2 with "no folder id for production".
- `.replace(..., 1)` replaces only the first match, so exactly one policy becomes a folder policy.

### `tests/unit/test_infrastructure_policy.py`

The guardrails over the Terraform text were quoted and explained in `regular-expressions.md` (the text search) and `iam-and-service-accounts.md` (the rules). The two remaining tests:

`tests/unit/test_infrastructure_policy.py`

```python
def test_the_environment_reads_the_same_files_the_tool_checks():
    main = (INFRA / "environments/lab/main.tf").read_text()
    assert 'file("${path.module}/../../../design/landing-zone.yaml")' in main
    assert 'file("${path.module}/../../../policies/org-policies.yaml")' in main


def test_the_terraform_test_literals_match_the_design_file(design):
    text = (INFRA / "environments/lab/tests/design.tftest.hcl").read_text()
    for subnet in design.subnets:
        assert f'"{subnet.name}" = "{subnet.cidr}"' in text
    for project in design.projects:
        assert f'"{project.name}" = "{project.name}-ab12cd"' in text


def test_the_environment_manages_exactly_the_constraints_of_the_policy_file(policies):
    text = (INFRA / "environments/lab/tests/design.tftest.hcl").read_text()
    for policy in policies:
        assert f"{policy.constraint}@organization" in text
    assert len(yaml.safe_load((ROOT / "policies/org-policies.yaml").read_text())["policies"]) == len(policies)
```

- The environment test checks `main.tf` reads both YAML files with `file("${path.module}/../../../...")`.
- The next two tests compare the literals in the Terraform test file with the design and the policies: for each subnet the text `"subnet-prod" = "10.50.0.0/24"` must be present, for each project `"prod-data" = "prod-data-ab12cd"`, for each policy `constraint@organization`, and the policy file must hold as many entries as the loaded tuple. The test cannot be fooled by a rename on one side only.

The whole file, for completeness:

`tests/unit/test_infrastructure_policy.py`

```python
"""Guardrails over the Terraform source, checked without Terraform or Google Cloud.

They encode the lesson's rules as tests: no keys, no broad roles, subnet-level network access, dry run as the default
for policies and the perimeter, and one source of truth (the YAML files) shared by Terraform and the landing-zone tool.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT / "infra"
SOURCES = {path: path.read_text() for path in INFRA.rglob("*.tf") if ".terraform" not in path.parts}
CODE = {path: re.sub(r"(?m)^\s*#.*$", "", text) for path, text in SOURCES.items()}
PROJECT_IAM = ["google_project_iam_member", "google_project_iam_binding", "google_project_iam_policy"]


def _hits(pattern: str) -> list[str]:
    return sorted(str(path.relative_to(INFRA)) for path, text in CODE.items() if re.search(pattern, text))


def test_the_sources_were_found():
    assert len(SOURCES) >= 30


def test_no_service_account_key_is_ever_created():
    assert _hits(r'resource\s+"google_service_account_key"') == []


@pytest.mark.parametrize("kind", PROJECT_IAM)
def test_project_level_roles_exist_only_for_the_lab_test_identities(kind):
    assert _hits(rf'resource\s+"{kind}"') in ([], ["modules/lab-identities/main.tf"])


@pytest.mark.parametrize("role", ["roles/owner", "roles/editor", "roles/compute.networkAdmin", "roles/compute.admin"])
def test_no_broad_role_appears(role):
    assert _hits(re.escape(role)) == []


def test_nothing_is_public():
    assert _hits("allUsers|allAuthenticatedUsers") == []


def test_network_user_is_granted_on_the_subnet_and_nowhere_else():
    assert _hits(r'role\s*=\s*"roles/compute.networkUser"') == ["modules/shared-vpc/main.tf"]
    assert "google_compute_subnetwork_iam_member" in (INFRA / "modules/shared-vpc/main.tf").read_text()


def test_policies_and_the_perimeter_default_to_dry_run():
    for path, variable in (
        ("modules/org-policies/variables.tf", "mode"),
        ("modules/perimeter/variables.tf", "mode"),
        ("environments/lab/variables.tf", "policy_mode"),
        ("environments/lab/variables.tf", "perimeter_mode"),
    ):
        block = re.search(rf'variable\s+"{variable}"\s*\{{(.*?)\n\}}', (INFRA / path).read_text(), re.S)
        assert block is not None, (path, variable)
        assert 'default     = "dry_run"' in block.group(1), (path, variable)


def test_the_perimeter_keeps_a_separate_dry_run_configuration():
    text = (INFRA / "modules/perimeter/main.tf").read_text()
    assert "use_explicit_dry_run_spec = true" in text
    assert 'for_each = var.mode == "enforced" ? [1] : []' in text


def test_every_policy_always_carries_a_dry_run_spec():
    text = (INFRA / "modules/org-policies/main.tf").read_text()
    assert "dry_run_spec {" in text
    assert 'for_each = var.mode == "enforced" ? [1] : []' in text


def test_the_environment_reads_the_same_files_the_tool_checks():
    main = (INFRA / "environments/lab/main.tf").read_text()
    assert 'file("${path.module}/../../../design/landing-zone.yaml")' in main
    assert 'file("${path.module}/../../../policies/org-policies.yaml")' in main


def test_the_terraform_test_literals_match_the_design_file(design):
    text = (INFRA / "environments/lab/tests/design.tftest.hcl").read_text()
    for subnet in design.subnets:
        assert f'"{subnet.name}" = "{subnet.cidr}"' in text
    for project in design.projects:
        assert f'"{project.name}" = "{project.name}-ab12cd"' in text


def test_the_environment_manages_exactly_the_constraints_of_the_policy_file(policies):
    text = (INFRA / "environments/lab/tests/design.tftest.hcl").read_text()
    for policy in policies:
        assert f"{policy.constraint}@organization" in text
    assert len(yaml.safe_load((ROOT / "policies/org-policies.yaml").read_text())["policies"]) == len(policies)


def test_the_provider_is_pinned_in_every_root_and_module():
    for path in INFRA.rglob("versions.tf"):
        if ".terraform" in path.parts:
            continue
        assert re.search(r'version\s*=\s*"(~>|>=)\s*8', path.read_text()), path
```

- `SOURCES` maps each Terraform file's path to its text; `CODE` is the same with comment lines removed. `@pytest.mark.parametrize("kind", PROJECT_IAM)` runs a test once per project-level IAM resource type; `@pytest.mark.parametrize("role", [...])` once per forbidden role. `in ([], ["modules/lab-identities/main.tf"])` accepts either list.
- `test_the_sources_were_found` asserts at least 30 Terraform files were read, so a wrong path cannot make every other test pass by finding nothing.

### `tests/unit/test_operating_notes.py`

`tests/unit/test_operating_notes.py`

```python
"""Step 6's Done when, as a test: the notes make the dry run mandatory and name a path the perimeter does not cover."""

from pathlib import Path

NOTES = (Path(__file__).resolve().parents[2] / "docs/operating-notes.md").read_text()


def test_the_notes_cover_the_exception_process_the_test_procedure_and_break_glass():
    for heading in (
        "## How a team requests an exception",
        "## How a change is tested (the dry run is mandatory)",
        "## What the perimeter does not protect against",
        "## Break glass",
    ):
        assert heading in NOTES


def test_the_dry_run_is_a_mandatory_step_before_enforcement():
    assert "No change to a policy or to the perimeter goes straight to enforcement" in NOTES
    assert "scripts/enforce.sh" in NOTES


def test_at_least_one_uncovered_path_is_named():
    assert "Data shown by an application" in NOTES
    assert "An insider with a legitimate access level" in NOTES
```

This test reads `docs/operating-notes.md` as text (`read_text()`) and checks four headings are present, that the dry run is declared mandatory and `scripts/enforce.sh` is named, and that two named uncovered paths ("Data shown by an application" and "An insider with a legitimate access level") appear. It is the lesson's step 6 as a test: a document can be tested too.

### `tests/e2e/test_cli_process.py`

`tests/e2e/test_cli_process.py`

```python
"""The installed `landing-zone` program as a user runs it: a subprocess in the repository root."""

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[2]


def run(*args):
    return subprocess.run(
        [sys.executable, "-m", "landing_zone.interfaces.cli", *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        cwd=ROOT,
    )


def test_make_design_runs_check_and_explain():
    assert "ok: the design" in run("check").stdout
    assert "A request it blocks" in run("explain").stdout


def test_the_lessons_attack_is_refused_when_enforced_and_only_logged_in_dry_run():
    enforced = run("simulate", "--mode", "enforced")
    dry = run("simulate", "--mode", "dry-run")
    assert enforced.returncode == 0
    assert (
        "copies customers.csv to a bucket outside the organization: REFUSED by vpc_service_controls" in enforced.stdout
    )
    assert dry.returncode == 0
    assert "copies customers.csv to a bucket outside the organization: allowed, but dry run would block" in dry.stdout


def test_policies_render_for_gcloud(tmp_path):
    result = run("render-policies", "--org", "123456789012", "--out", str(tmp_path))
    assert result.returncode == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "compute.vmExternalIpAccess.yaml",
        "gcp.resourceLocations.yaml",
        "iam.disableServiceAccountKeyCreation.yaml",
        "storage.uniformBucketLevelAccess.yaml",
    ]
```

- A **process** is a running program. `subprocess.run([...])` starts a new one and waits for it. The list is the command: `sys.executable` is the path of the Python that is running the tests, `-m landing_zone.interfaces.cli` runs a module as a program, and `*args` adds the arguments.
- `capture_output=True` collects what the program prints; `text=True` gives text instead of bytes; `timeout=60` kills it after 60 seconds; `check=False` means a non-zero exit status does not raise an exception (the tests read `returncode` themselves); `cwd=ROOT` runs it in the repository root so the default file paths work.
- `pytestmark = pytest.mark.e2e` puts every test of the file in the `e2e` group declared in `pyproject.toml` (the `-m e2e` option selects it).
- The three tests: `check` and `explain` work as a real program; the attack is refused when enforced and only logged in dry run (the key sentences are searched in `stdout`); `render-policies --out tmp_path` writes exactly the four expected files (`sorted(p.name for p in tmp_path.iterdir())`).

## 6. Try it yourself

```bash
make test-python
```
Expected: a line of dots, then a coverage table ending with `TOTAL` and a pass count such as `98 passed`.

```bash
.venv/bin/python -m pytest tests/unit -q -p no:cacheprovider -k "perimeter or dry_run"
```
Expected: only the tests whose names contain the words run; the others show as deselected.

```bash
.venv/bin/python -m pytest tests/unit --collect-only -q -p no:cacheprovider | tail -3
```
Expected: the last lines list test ids and a count like `98 tests collected`.

```bash
.venv/bin/python -m coverage report --include='src/landing_zone/domain/*,src/landing_zone/application/*' --fail-under=95 | tail -3
```
Expected: a `TOTAL` line at or above 95% (run `make test-python` first so coverage data exists).

## 7. Mistakes people make

- **Tests that need the network or the cloud.** These are slow and flaky; this repository keeps them in a separate folder and behind markers or containers.
- **Tests that depend on each other's order.** Each test builds its own world.
- **Asserting too little** (`assert result`) or too much (every field of a huge object). Assert the behavior the test name states.
- **Chasing 100% coverage.** Coverage shows what was not run; it does not prove the checks were good.
- **Forgetting that a hidden bug can sit on a path no test takes.** This project once had a logging bug visible only at INFO level; a regression test now runs at INFO.

## 8. Check yourself

1. How does pytest decide something is a test? *File named `test_*.py`, function named `test_*`.*
2. What is a fixture? *A setup function whose result is passed to tests by name.*
3. What does `parametrize` do? *Runs one test with several inputs.*
4. What does `--strict-markers` prevent? *Silent typos in marker names.*
5. What does `branch = true` add to coverage? *Whether both outcomes of each condition ran.*

## 9. Further reading

- pytest documentation: <https://docs.pytest.org/en/stable/>
- Fixtures: <https://docs.pytest.org/en/stable/how-to/fixtures.html>
- Parametrize: <https://docs.pytest.org/en/stable/how-to/parametrize.html>
- Coverage.py: <https://coverage.readthedocs.io/>
- pytest-cov: <https://pytest-cov.readthedocs.io/>
