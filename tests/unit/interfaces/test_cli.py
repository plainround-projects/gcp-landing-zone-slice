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
