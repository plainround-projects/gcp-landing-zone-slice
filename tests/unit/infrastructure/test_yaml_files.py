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
