# Regular expressions (the `re` module and Terraform's `regex`)

## 1. What it is

A **regular expression** (regex) is a compact pattern that describes text: "digits only", "a word, then `@`, then a domain". Python's standard module `re` compiles a pattern and tests or searches text with it. Patterns are written in a small language of their own: `[0-9]` is one digit, `+` means "one or more", `.` is any character, `\s` is any white-space character, `(.*?)` captures as little text as possible, `^` and `$` are the start and end. Terraform has its own `regex()` function with a similar pattern language (RE2).

## 2. Why this repository uses it

Two jobs. First, input checks in Terraform: an organization id must be digits only, a name suffix must be 3 to 6 lowercase letters or digits. Second, guardrail tests that read the Terraform source as plain text and fail if it contains something the lesson forbids: a service account key resource, a broad role, a public member, a missing `dry_run` default.

## 3. Where it appears

| Path | What it does |
| --- | --- |
| `tests/unit/test_infrastructure_policy.py` | Searches the `.tf` files with `re.search` and strips comments with `re.sub`. |
| `infra/environments/lab/variables.tf` | `regex("^[0-9]+$", var.org_id)` and `regex("^[a-z0-9]{3,6}$", var.name_suffix)` in `validation` blocks. |

## 4. How it works underneath

`re.search(pattern, text)` looks for the pattern anywhere and returns a **match object** (or `None`). `re.fullmatch` demands that the whole string match. `re.sub(pattern, replacement, text)` replaces every match. A match object gives the matched text with `.group(1)` for the first parenthesized part.

**Flags** change the rules. `(?m)` (multi-line) lets `^` and `$` match at every line, not just the start and end of the text. `re.S` lets `.` match a line break too. A pattern is a plain string, so write it as a **raw string** (`r"..."`) to stop Python from treating backslashes as its own escapes. `rf'...'` is a raw f-string: a raw string with `{values}` filled in; a literal brace is then written twice (`\{{`).

In Terraform, `regex(pattern, text)` returns the match and **fails** when there is none, so the validation wraps it in `can(...)`, which turns "failed" into `false`.

## 5. Walkthrough of this repository's use

Terraform's input checks:

`infra/environments/lab/variables.tf`

```hcl
variable "org_id" {
  description = "Organization id (gcloud organizations list). A free Cloud Identity domain gives you one."
  type        = string

  validation {
    condition     = can(regex("^[0-9]+$", var.org_id))
    error_message = "org_id must contain digits only."
  }
}
```

`can(regex("^[0-9]+$", var.org_id))` is true only when the whole text is one or more digits. A domain name pasted by mistake fails the check at plan time and shows the message.

`infra/environments/lab/variables.tf`

```hcl
variable "name_suffix" {
  description = "Appended to project ids and the bucket name, which are global: 3 to 6 lowercase letters or digits."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{3,6}$", var.name_suffix))
    error_message = "name_suffix must be 3 to 6 lowercase letters or digits."
  }
}
```

`^[a-z0-9]{3,6}$`: from the start to the end, between 3 and 6 characters, each a lowercase letter or digit. The anchors `^` and `$` are what stop `Bad Suffix` or `ab12cd-extra` from sneaking through.

The guardrail tests prepare the text once:

`tests/unit/test_infrastructure_policy.py`

```python
SOURCES = {path: path.read_text() for path in INFRA.rglob("*.tf") if ".terraform" not in path.parts}
CODE = {path: re.sub(r"(?m)^\s*#.*$", "", text) for path, text in SOURCES.items()}
PROJECT_IAM = ["google_project_iam_member", "google_project_iam_binding", "google_project_iam_policy"]


def _hits(pattern: str) -> list[str]:
    return sorted(str(path.relative_to(INFRA)) for path, text in CODE.items() if re.search(pattern, text))
```

- `INFRA.rglob("*.tf")` finds every Terraform file below `infra/`, skipping any inside a downloaded `.terraform` folder.
- `re.sub(r"(?m)^\s*#.*$", "", text)` deletes comment lines: optional white space, `#`, the rest of the line. A comment that mentions `roles/owner` must not fail the test.
- `_hits(pattern)` lists the files whose code matches.

Then each rule is one pattern:

`tests/unit/test_infrastructure_policy.py`

```python
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
```

- `resource\s+"google_service_account_key"`: the word `resource`, one or more spaces, then that quoted type. `\s+` tolerates any spacing.
- `rf'resource\s+"{kind}"'` inserts each project-level IAM resource type in turn.
- `re.escape(role)` makes a role name safe to use as a pattern: the dots in `roles/compute.admin` would otherwise match any character.
- `"allUsers|allAuthenticatedUsers"`: the bar means "or".

A block is extracted by pattern too:

`tests/unit/test_infrastructure_policy.py`

```python
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
```

`variable\s+"mode"\s*\{(.*?)\n\}` finds `variable "mode" {`, then captures lazily (`.*?`, with `re.S` so it crosses lines) up to the first closing brace at the start of a line. `block.group(1)` is the text between. The test then asserts it contains the default.

The version pin:

`tests/unit/test_infrastructure_policy.py`

```python
def test_the_provider_is_pinned_in_every_root_and_module():
    for path in INFRA.rglob("versions.tf"):
        if ".terraform" in path.parts:
            continue
        assert re.search(r'version\s*=\s*"(~>|>=)\s*8', path.read_text()), path
```

`version\s*=\s*"(~>|>=)\s*8` accepts `version = "~> 8.8"` and `version = ">= 8.0, < 9.0"` and rejects an older major version.

## 6. Try it yourself

```bash
.venv/bin/python -c "
import re
print(bool(re.fullmatch(r'[a-z0-9]{3,6}', 'ab12cd')), bool(re.fullmatch(r'[a-z0-9]{3,6}', 'Bad Suffix')))"
```
Expected: `True False`

```bash
.venv/bin/python -c "
import re
text = '# a comment\nrole = \"roles/owner\"\n   # another\nx = 1\n'
print(repr(re.sub(r'(?m)^\s*#.*\$', '', text)))
print(repr(re.sub(r'^\s*#.*\$', '', text)))"
```
Expected: the first line shows both comment lines gone (`'\nrole = "roles/owner"\n\nx = 1\n'`); the second, without `(?m)`, leaves the text unchanged because `^` and `$` match only at the very start and end of the whole text.

```bash
.venv/bin/python -c "
import re
t = 'variable \"mode\" {\n  default     = \"dry_run\"\n}\nvariable \"other\" {\n}\n'
print(repr(re.search(r'variable\s+\"mode\"\s*\{(.*?)\n\}', t, re.S).group(1)))"
```
Expected: `'\n  default     = "dry_run"'`

```bash
.venv/bin/python -m pytest tests/unit/test_infrastructure_policy.py -q -p no:cacheprovider
```
Expected: `18 passed` (some tests run once per role or resource kind).

```bash
cd infra/environments/lab && terraform init -backend=false -input=false >/dev/null && terraform test -filter=tests/design.tftest.hcl | tail -2
```
Expected: ends with `Success! 7 passed, 0 failed.` Two of the seven runs (`a_bad_suffix_is_rejected` and `a_non_numeric_org_id_is_rejected`) pass only because the regex validation fails as intended.

## 7. Mistakes people make

- **Forgetting the raw string**, so `\.` or `\s` becomes something else.
- **Using `.search` when the whole string must match.** Use `.fullmatch` or anchors.
- **No anchors in a validation** (`[0-9]+` instead of `^[0-9]+$`), which accepts `abc123def`.
- **Greedy matching** (`.*`) swallowing too much. A `?` after the quantifier makes it lazy.
- **Unescaped dots.** `roles/compute.admin` as a pattern also matches `roles/computeXadmin`. Use `re.escape`.
- **Parsing Terraform with regular expressions in production code.** Here it is only a cheap guardrail in tests; real analysis belongs to tools that parse the language (`tflint`, `checkov`).

## 8. Check yourself

1. What is the difference between `search` and `fullmatch`? *`search` finds the pattern anywhere; `fullmatch` needs the whole string to match.*
2. What does `(?m)` do? *Makes `^` and `$` match at every line.*
3. Why is `regex(...)` wrapped in `can(...)`? *`regex` fails when nothing matches; `can` turns that into `false`.*
4. What does `re.escape("roles/compute.admin")` protect against? *The dot matching any character.*
5. What does `.*?` mean? *Any characters, as few as possible.*

## 9. Further reading

- `re` module: <https://docs.python.org/3.12/library/re.html>
- Regular expression HOWTO: <https://docs.python.org/3.12/howto/regex.html>
- Terraform `regex` function: <https://developer.hashicorp.com/terraform/language/functions/regex>
- RE2 syntax (used by Terraform): <https://github.com/google/re2/wiki/Syntax>
