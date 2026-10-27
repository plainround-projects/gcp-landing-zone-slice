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
