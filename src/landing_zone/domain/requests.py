"""The requests the lesson makes, as immutable values the decision rules can evaluate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateServiceAccountKey:
    """Download a key for a service account in `project`."""

    project: str


@dataclass(frozen=True, slots=True)
class CreateBucket:
    """Create a bucket in `project` at `location` (`europe-west1`, `us-central1`, `EU`...)."""

    project: str
    location: str
    uniform_access: bool


@dataclass(frozen=True, slots=True)
class CreateVm:
    """Create a VM in `project`; `subnet` is a subnet of the shared VPC, `caller_groups` the groups of the caller."""

    project: str
    zone: str
    subnet: str | None
    external_ip: bool
    caller_groups: frozenset[str]


@dataclass(frozen=True, slots=True)
class CopyObject:
    """Copy an object from a bucket in `source_project` to one in `destination_project`."""

    caller_can_read: bool
    source_project: str
    destination_project: str


@dataclass(frozen=True, slots=True)
class ReadObject:
    """Read an object in `project`; `from_access_level` names the access level the caller's address matches, if any."""

    caller_can_read: bool
    project: str
    from_access_level: str | None


Request = CreateServiceAccountKey | CreateBucket | CreateVm | CopyObject | ReadObject
