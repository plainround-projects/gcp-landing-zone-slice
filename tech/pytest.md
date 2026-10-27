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
