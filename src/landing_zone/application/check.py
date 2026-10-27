"""Consistency checks over the design and the policies together."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from landing_zone.domain.design import Design, validate_design
from landing_zone.domain.policy import OrgPolicy

REQUIRED_CONSTRAINTS = (
    "iam.disableServiceAccountKeyCreation",
    "gcp.resourceLocations",
    "storage.uniformBucketLevelAccess",
    "compute.vmExternalIpAccess",
)


def check(design: Design, policies: Sequence[OrgPolicy]) -> list[str]:
    """Every problem found, design first. The policy type already enforces a reason and a blocked request."""
    problems = validate_design(design)
    counts = Counter((p.constraint, p.level) for p in policies)
    problems += [f"policy {constraint} is set twice at {level}" for (constraint, level), n in counts.items() if n > 1]
    for policy in policies:
        if policy.folder is not None and policy.folder not in design.folders:
            problems.append(f"policy {policy.constraint} is set on unknown folder {policy.folder}")
    present = {p.constraint for p in policies}
    problems += [
        f"the lesson's policy {constraint} is missing"
        for constraint in REQUIRED_CONSTRAINTS
        if constraint not in present
    ]
    return problems
