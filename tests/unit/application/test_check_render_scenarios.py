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
