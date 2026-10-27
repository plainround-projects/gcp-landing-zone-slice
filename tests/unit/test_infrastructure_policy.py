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
