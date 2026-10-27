"""Shared fixtures: the repository's real design and policies, loaded once, plus builders for small variations."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from landing_zone.domain.design import Design
from landing_zone.domain.policy import OrgPolicy
from landing_zone.infrastructure.yaml_files import load_design, load_policies

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def design() -> Design:
    return load_design(ROOT / "design/landing-zone.yaml")


@pytest.fixture(scope="session")
def policies() -> tuple[OrgPolicy, ...]:
    return load_policies(ROOT / "policies/org-policies.yaml")


@pytest.fixture
def without(design):
    """A copy of the design with some fields replaced."""

    def build(**changes):
        return replace(design, **changes)

    return build
