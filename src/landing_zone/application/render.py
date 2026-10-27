"""Turn policies into the documents `gcloud org-policies set-policy` takes, and into a table people can read."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from landing_zone.domain.policy import OrgPolicy, PolicyKind


def render_policy_document(
    policy: OrgPolicy, organization_id: str, *, dry_run: bool, folder_ids: dict[str, str] | None = None
) -> dict[str, Any]:
    """One policy as the dict behind the gcloud YAML; `dry_run` writes `dryRunSpec` so the policy only logs."""
    parent = f"organizations/{organization_id}"
    if policy.folder is not None:
        folder_id = (folder_ids or {}).get(policy.folder)
        if folder_id is None:
            raise KeyError(f"no folder id for {policy.folder}: pass it with --folder NAME=ID")
        parent = f"folders/{folder_id}"
    if policy.kind is PolicyKind.BOOLEAN:
        rule: dict[str, Any] = {"enforce": policy.enforce}
    elif policy.deny_all:
        rule = {"denyAll": True}
    else:
        rule = {"values": {"allowedValues": list(policy.allowed_values)}}
    return {"name": f"{parent}/policies/{policy.constraint}", "dryRunSpec" if dry_run else "spec": {"rules": [rule]}}


def explain(policies: Sequence[OrgPolicy]) -> str:
    """A Markdown table of constraint, level, reason and the request each policy blocks (step 1's Done when)."""
    lines = ["| Constraint | Level | Reason | A request it blocks | Instead |", "| --- | --- | --- | --- | --- |"]
    for policy in policies:
        cells = (f"`{policy.constraint}`", policy.level, policy.reason, policy.blocked_request, policy.instead)
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
    return "\n".join(lines) + "\n"
