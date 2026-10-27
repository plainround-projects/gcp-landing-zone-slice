"""The `landing-zone` command: check the design, explain the policies, render them for gcloud, simulate requests."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from landing_zone.application.check import check
from landing_zone.application.render import explain, render_policy_document
from landing_zone.application.scenarios import format_results, run_scenarios
from landing_zone.domain.decision import PerimeterMode
from landing_zone.domain.errors import DomainError
from landing_zone.domain.landscape import Landscape
from landing_zone.infrastructure.yaml_files import (
    load_design,
    load_policies,
    load_scenarios,
    write_policy_documents,
)

DESIGN = Path("design/landing-zone.yaml")
POLICIES = Path("policies/org-policies.yaml")
SCENARIOS = Path("design/scenarios.yaml")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command; returns the exit status (0 ok, 1 a check or scenario failed, 2 unreadable input)."""
    args = _parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (DomainError, OSError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="landing-zone", description=__doc__)
    parser.add_argument("--design", type=Path, default=DESIGN)
    parser.add_argument("--policies", type=Path, default=POLICIES)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("check", help="check the design and the policies are consistent").set_defaults(handler=_check)
    commands.add_parser("explain", help="print each policy with its reason and the request it blocks").set_defaults(
        handler=_explain
    )

    render = commands.add_parser("render-policies", help="write the YAML that `gcloud org-policies set-policy` takes")
    render.add_argument("--org", required=True, help="the organization id (gcloud organizations list)")
    render.add_argument("--out", type=Path, default=Path("build/org-policies"))
    render.add_argument(
        "--dry-run", action="store_true", help="write dryRunSpec: the policy logs violations and blocks nothing"
    )
    render.add_argument(
        "--folder", action="append", default=[], metavar="NAME=ID", help="folder id for a folder-level policy"
    )
    render.set_defaults(handler=_render)

    simulate = commands.add_parser(
        "simulate", help="run design/scenarios.yaml and show which control answers each request"
    )
    simulate.add_argument("--mode", choices=[m.value for m in PerimeterMode], default=PerimeterMode.ENFORCED.value)
    simulate.add_argument("--scenarios", type=Path, default=SCENARIOS)
    simulate.set_defaults(handler=_simulate)
    return parser


def _check(args: argparse.Namespace) -> int:
    problems = check(load_design(args.design), load_policies(args.policies))
    for problem in problems:
        print(f"problem: {problem}")
    if not problems:
        print("ok: the design and the policies are consistent")
    return 1 if problems else 0


def _explain(args: argparse.Namespace) -> int:
    print(explain(load_policies(args.policies)), end="")
    return 0


def _render(args: argparse.Namespace) -> int:
    folder_ids = dict(item.split("=", 1) for item in args.folder)
    policies = load_policies(args.policies)
    documents = [
        (policy.constraint, render_policy_document(policy, args.org, dry_run=args.dry_run, folder_ids=folder_ids))
        for policy in policies
    ]
    for path in write_policy_documents(args.out, documents):
        print(path)
    return 0


def _simulate(args: argparse.Namespace) -> int:
    landscape = Landscape(load_design(args.design), load_policies(args.policies), PerimeterMode(args.mode))
    results = run_scenarios(landscape, load_scenarios(args.scenarios))
    print(format_results(results), end="")
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
