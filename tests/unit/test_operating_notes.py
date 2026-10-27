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
