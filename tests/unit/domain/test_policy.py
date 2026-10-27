import pytest

from landing_zone.domain.errors import InvalidPolicy
from landing_zone.domain.policy import OrgPolicy, PolicyKind


def policy(**overrides):
    values = {
        "constraint": "iam.disableServiceAccountKeyCreation",
        "kind": PolicyKind.BOOLEAN,
        "level": "organization",
        "reason": "no downloadable keys",
        "blocked_request": "a key for a laptop script",
        "instead": "impersonate",
        "enforce": True,
    }
    return OrgPolicy(**{**values, **overrides})


def test_the_repositorys_policies_each_have_a_reason_and_a_blocked_request(policies):
    assert len(policies) == 4
    assert all(p.reason and p.blocked_request and p.instead for p in policies)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"constraint": ""}, "not a constraint name"),
        ({"constraint": "a/b"}, "not a constraint name"),
        ({"reason": "  "}, "no reason"),
        ({"blocked_request": ""}, "blocks"),
        ({"instead": ""}, "blocks"),
        ({"level": "project:x"}, "level must be"),
        ({"allowed_values": ("x",)}, "boolean constraint takes only enforce"),
        ({"deny_all": True}, "boolean constraint takes only enforce"),
        ({"kind": PolicyKind.LIST, "enforce": True, "allowed_values": ("x",)}, "not enforce"),
        ({"kind": PolicyKind.LIST, "enforce": False}, "exactly one of"),
        ({"kind": PolicyKind.LIST, "enforce": False, "allowed_values": ("x",), "deny_all": True}, "exactly one of"),
    ],
)
def test_incomplete_or_contradictory_policies_are_rejected_with_the_constraint_named(overrides, message):
    with pytest.raises(InvalidPolicy, match=message):
        policy(**overrides)


def test_a_folder_policy_applies_only_to_its_folder_and_an_organization_policy_to_all():
    assert policy(level="folder:production").folder == "production"
    assert policy(level="folder:production").applies_to_folder("production")
    assert not policy(level="folder:production").applies_to_folder("shared")
    assert policy().folder is None
    assert policy().applies_to_folder("anything")
