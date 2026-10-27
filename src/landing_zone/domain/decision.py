"""Which control stops a request: the answer and the evidence, as values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Control(Enum):
    """The four things that can stop a request in this landing zone."""

    ORG_POLICY = "org_policy"
    SHARED_VPC_IAM = "shared_vpc_iam"
    VPC_SERVICE_CONTROLS = "vpc_service_controls"
    IAM = "iam"


class PerimeterMode(Enum):
    """A dry-run perimeter logs violations; an enforced one refuses the call."""

    DRY_RUN = "dry-run"
    ENFORCED = "enforced"


@dataclass(frozen=True, slots=True)
class Violation:
    """One control that objects: which one, the constraint, permission or reason code, and the message it gives."""

    control: Control
    detail: str
    message: str


@dataclass(frozen=True, slots=True)
class Decision:
    """The outcome for one request. `logged_only` holds dry-run violations that were recorded but did not block."""

    violations: tuple[Violation, ...] = ()
    logged_only: tuple[Violation, ...] = ()

    @property
    def allowed(self) -> bool:
        """True when no control refuses the request."""
        return not self.violations

    @property
    def stopped_by(self) -> Violation | None:
        """The first violation, which is the control that stops the request."""
        return self.violations[0] if self.violations else None
