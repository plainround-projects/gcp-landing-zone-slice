"""Adapter: read the design, the policies and the scenarios from YAML files; write policy documents."""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from landing_zone.application.scenarios import Expectation, Scenario
from landing_zone.domain.decision import Control
from landing_zone.domain.design import AccessLevel, Design, Perimeter, Project, ProjectRole, SensitiveData, Subnet
from landing_zone.domain.errors import InvalidDesign, InvalidPolicy, InvalidRequest
from landing_zone.domain.policy import OrgPolicy, PolicyKind
from landing_zone.domain.requests import (
    CopyObject,
    CreateBucket,
    CreateServiceAccountKey,
    CreateVm,
    ReadObject,
    Request,
)


def load_design(path: Path) -> Design:
    """Parse `landing-zone.yaml`; raises `InvalidDesign` for a missing key or a malformed value."""
    data = _load(path)
    try:
        vpc = data["shared_vpc"]
        perimeter = data["perimeter"]
        sensitive = data["sensitive_data"]
        return Design(
            domain=str(data["organization"]["domain"]),
            folders=tuple(str(f["name"]) for f in data["folders"]),
            projects=tuple(Project(str(p["name"]), str(p["folder"]), ProjectRole(p["role"])) for p in data["projects"]),
            host_project=str(vpc["host_project"]),
            network=str(vpc["network"]),
            region=str(vpc["region"]),
            subnets=tuple(
                Subnet(
                    str(s["name"]),
                    ipaddress.IPv4Network(s["cidr"]),
                    str(s["service_project"]),
                    tuple(str(g) for g in s.get("user_groups", [])),
                )
                for s in vpc["subnets"]
            ),
            perimeter=Perimeter(
                str(perimeter["name"]),
                str(perimeter["title"]),
                tuple(str(p) for p in perimeter["projects"]),
                tuple(str(s) for s in perimeter["restricted_services"]),
                tuple(str(a) for a in perimeter.get("access_levels", [])),
            ),
            access_levels=tuple(
                AccessLevel(str(a["name"]), tuple(ipaddress.IPv4Network(n) for n in a["ip_subnetworks"]))
                for a in data.get("access_levels", [])
            ),
            sensitive=SensitiveData(str(sensitive["project"]), str(sensitive["bucket"]), str(sensitive["object"])),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidDesign(f"{path}: {type(error).__name__}: {error}") from error


def load_policies(path: Path) -> tuple[OrgPolicy, ...]:
    """Parse `org-policies.yaml`; `InvalidPolicy` says which entry is wrong and why."""
    data = _load(path)
    try:
        return tuple(_policy(entry) for entry in data["policies"])
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidPolicy(f"{path}: {type(error).__name__}: {error}") from error


def _policy(entry: Mapping[str, Any]) -> OrgPolicy:
    blocks = entry["blocks"]
    return OrgPolicy(
        constraint=str(entry["constraint"]),
        kind=PolicyKind(entry["kind"]),
        level=str(entry.get("level", "organization")),
        reason=str(entry["reason"]),
        blocked_request=str(blocks["request"]),
        instead=str(blocks["instead"]),
        enforce=bool(entry.get("enforce", False)),
        allowed_values=tuple(str(v) for v in entry.get("allowed_values", [])),
        deny_all=bool(entry.get("deny_all", False)),
    )


def load_scenarios(path: Path) -> tuple[Scenario, ...]:
    """Parse `scenarios.yaml`; `InvalidRequest` names the scenario that cannot be understood."""
    data = _load(path)
    scenarios = []
    for entry in data.get("scenarios", []):
        name = str(entry.get("name", "?"))
        try:
            expect = entry["expect"]
            control = Control(expect["control"]) if "control" in expect else None
            expectation = Expectation(bool(expect["allowed"]), control, expect.get("detail"))
            scenarios.append(Scenario(name, _request(entry["request"]), expectation))
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidRequest(f"scenario {name!r}: {type(error).__name__}: {error}") from error
    return tuple(scenarios)


def _request(raw: Mapping[str, Any]) -> Request:
    kind = raw["type"]
    if kind == "create_service_account_key":
        return CreateServiceAccountKey(str(raw["project"]))
    if kind == "create_bucket":
        return CreateBucket(str(raw["project"]), str(raw["location"]), bool(raw["uniform_access"]))
    if kind == "create_vm":
        subnet = raw.get("subnet")
        return CreateVm(
            str(raw["project"]),
            str(raw["zone"]),
            None if subnet is None else str(subnet),
            bool(raw["external_ip"]),
            frozenset(str(g) for g in raw.get("caller_groups", [])),
        )
    if kind == "copy_object":
        return CopyObject(bool(raw["caller_can_read"]), str(raw["source_project"]), str(raw["destination_project"]))
    if kind == "read_object":
        level = raw.get("from_access_level")
        return ReadObject(bool(raw["caller_can_read"]), str(raw["project"]), None if level is None else str(level))
    raise ValueError(f"unknown request type {kind!r}")


def write_policy_documents(directory: Path, documents: Sequence[tuple[str, Mapping[str, Any]]]) -> list[Path]:
    """Write each (file stem, document) as `<stem>.yaml` under `directory`, creating it; returns the paths."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for stem, document in documents:
        path = directory / f"{stem}.yaml"
        path.write_text(yaml.safe_dump(dict(document), sort_keys=False), encoding="utf-8")
        paths.append(path)
    return paths


def _load(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise InvalidDesign(f"{path}: not valid YAML: {error}") from error
    if not isinstance(data, dict):
        raise InvalidDesign(f"{path}: expected a mapping at the top level")
    return data
