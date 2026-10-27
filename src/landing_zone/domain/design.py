"""The landing-zone slice as immutable values: folders, projects, the shared VPC and the perimeter."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from enum import Enum


class ProjectRole(Enum):
    """What a project is for."""

    DATA = "data"
    SERVICE = "service"
    HOST = "host"


@dataclass(frozen=True, slots=True)
class Project:
    """A project and the folder it sits in."""

    name: str
    folder: str
    role: ProjectRole


@dataclass(frozen=True, slots=True)
class Subnet:
    """A subnet of the shared VPC, the service project that uses it and the groups allowed to use it."""

    name: str
    cidr: ipaddress.IPv4Network
    service_project: str
    user_groups: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AccessLevel:
    """Callers from these address ranges count as inside the organization's trusted network."""

    name: str
    ip_subnetworks: tuple[ipaddress.IPv4Network, ...]


@dataclass(frozen=True, slots=True)
class Perimeter:
    """A VPC Service Controls perimeter around some projects and some services."""

    name: str
    title: str
    projects: tuple[str, ...]
    restricted_services: tuple[str, ...]
    access_levels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SensitiveData:
    """Where the data the perimeter protects lives."""

    project: str
    bucket: str
    object_name: str


@dataclass(frozen=True, slots=True)
class Design:
    """The whole slice."""

    domain: str
    folders: tuple[str, ...]
    projects: tuple[Project, ...]
    host_project: str
    network: str
    region: str
    subnets: tuple[Subnet, ...]
    perimeter: Perimeter
    access_levels: tuple[AccessLevel, ...]
    sensitive: SensitiveData

    def project(self, name: str) -> Project | None:
        """The project called `name`, or None when the design has none."""
        return next((p for p in self.projects if p.name == name), None)

    def subnet(self, name: str) -> Subnet | None:
        """The subnet called `name`, or None."""
        return next((s for s in self.subnets if s.name == name), None)


def validate_design(design: Design) -> list[str]:
    """Return every structural problem of the design, in a stable order; an empty list means it is consistent."""
    problems: list[str] = []
    problems += _duplicates("folder", design.folders)
    problems += _duplicates("project", [p.name for p in design.projects])
    problems += _duplicates("subnet", [s.name for s in design.subnets])
    problems += _duplicates("access level", [a.name for a in design.access_levels])

    for project in design.projects:
        if project.folder not in design.folders:
            problems.append(f"project {project.name} is in unknown folder {project.folder}")

    host = design.project(design.host_project)
    if host is None:
        problems.append(f"host project {design.host_project} is not a project")
    elif host.role is not ProjectRole.HOST:
        problems.append(f"host project {host.name} must have role host")
    if sum(1 for p in design.projects if p.role is ProjectRole.HOST) != 1:
        problems.append("exactly one project must have role host")

    for subnet in design.subnets:
        service = design.project(subnet.service_project)
        if service is None or service.role is not ProjectRole.SERVICE:
            problems.append(f"subnet {subnet.name} names {subnet.service_project}, which is not a service project")
        if not subnet.user_groups:
            problems.append(f"subnet {subnet.name} has no user group, so nobody may use it")
    problems += _overlaps(design.subnets)

    for name in design.perimeter.projects:
        if design.project(name) is None:
            problems.append(f"perimeter project {name} is not a project")
    if not design.perimeter.projects:
        problems.append("the perimeter protects no project")
    if not design.perimeter.restricted_services:
        problems.append("the perimeter restricts no service")
    known_levels = {a.name for a in design.access_levels}
    for level in design.perimeter.access_levels:
        if level not in known_levels:
            problems.append(f"perimeter uses unknown access level {level}")

    if design.sensitive.project not in design.perimeter.projects:
        problems.append(f"sensitive data is in {design.sensitive.project}, which is outside the perimeter")
    return problems


def _duplicates(kind: str, names: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        if name in seen:
            out.append(f"duplicate {kind} {name}")
        seen.add(name)
    return out


def _overlaps(subnets: tuple[Subnet, ...]) -> list[str]:
    out = []
    for index, first in enumerate(subnets):
        for second in subnets[index + 1 :]:
            if first.cidr.overlaps(second.cidr):
                out.append(f"subnets {first.name} ({first.cidr}) and {second.name} ({second.cidr}) overlap")
    return out
