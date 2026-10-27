"""Organization policies: a constraint, how it is set, why, and which team request it blocks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from landing_zone.domain.errors import InvalidPolicy


class PolicyKind(Enum):
    """Boolean constraints are enforced or not; list constraints allow some values or deny all."""

    BOOLEAN = "boolean"
    LIST = "list"


@dataclass(frozen=True, slots=True)
class OrgPolicy:
    """One organization policy entry of `policies/org-policies.yaml`."""

    constraint: str
    kind: PolicyKind
    level: str
    reason: str
    blocked_request: str
    instead: str
    enforce: bool = False
    allowed_values: tuple[str, ...] = ()
    deny_all: bool = False

    def __post_init__(self) -> None:
        """Reject entries that are incomplete for their kind or cannot be defended."""
        if not self.constraint or "/" in self.constraint:
            raise InvalidPolicy(f"not a constraint name: {self.constraint!r}")
        if not self.reason.strip():
            raise InvalidPolicy(f"{self.constraint}: a policy with no reason is a rule you cannot defend")
        if not self.blocked_request.strip() or not self.instead.strip():
            raise InvalidPolicy(f"{self.constraint}: name one team request it blocks and what to do instead")
        if self.level != "organization" and not self.level.startswith("folder:"):
            raise InvalidPolicy(f"{self.constraint}: level must be 'organization' or 'folder:NAME', got {self.level!r}")
        if self.kind is PolicyKind.BOOLEAN and (self.allowed_values or self.deny_all):
            raise InvalidPolicy(f"{self.constraint}: a boolean constraint takes only enforce")
        if self.kind is PolicyKind.LIST:
            if self.enforce:
                raise InvalidPolicy(
                    f"{self.constraint}: a list constraint takes allowed_values or deny_all, not enforce"
                )
            if bool(self.allowed_values) == self.deny_all:
                raise InvalidPolicy(f"{self.constraint}: give exactly one of allowed_values and deny_all")

    @property
    def folder(self) -> str | None:
        """The folder name for a folder-level policy, None for the organization."""
        return self.level.removeprefix("folder:") if self.level.startswith("folder:") else None

    def applies_to_folder(self, folder: str) -> bool:
        """An organization policy applies to every folder; a folder policy only to its own."""
        return self.folder is None or self.folder == folder
