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
