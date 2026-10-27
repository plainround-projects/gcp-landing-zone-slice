import ipaddress
from dataclasses import replace

from landing_zone.domain.design import Project, ProjectRole, Subnet, validate_design


def test_the_repositorys_design_is_consistent(design):
    assert validate_design(design) == []


def test_lookup_helpers_return_none_for_unknown_names(design):
    assert design.project("prod-data").folder == "production"
    assert design.project("nope") is None
    assert design.subnet("subnet-dev").cidr == ipaddress.ip_network("10.60.0.0/24")
    assert design.subnet("nope") is None


def test_duplicate_names_are_reported(without, design):
    problems = validate_design(without(folders=("a", "a"), projects=(*design.projects, design.projects[0])))
    assert "duplicate folder a" in problems
    assert "duplicate project prod-data" in problems


def test_a_project_in_an_unknown_folder_is_reported(without, design):
    stray = Project("stray", "nowhere", ProjectRole.SERVICE)
    assert "project stray is in unknown folder nowhere" in validate_design(without(projects=(*design.projects, stray)))


def test_overlapping_subnets_are_reported(without, design):
    first, second = design.subnets
    clash = replace(second, cidr=ipaddress.ip_network("10.50.0.128/25"))
    problems = validate_design(without(subnets=(first, clash)))
    assert any("overlap" in p for p in problems)


def test_a_subnet_without_users_or_a_service_project_is_reported(without, design):
    orphan = Subnet("subnet-x", ipaddress.IPv4Network("10.70.0.0/24"), "net-host", ())
    problems = validate_design(without(subnets=(*design.subnets, orphan)))
    assert "subnet subnet-x names net-host, which is not a service project" in problems
    assert "subnet subnet-x has no user group, so nobody may use it" in problems


def test_the_host_project_must_exist_and_be_the_only_host(without, design):
    assert any("is not a project" in p for p in validate_design(without(host_project="ghost")))
    second_host = Project("net-2", "shared", ProjectRole.HOST)
    assert "exactly one project must have role host" in validate_design(
        without(projects=(*design.projects, second_host))
    )
    wrong_role = tuple(replace(p, role=ProjectRole.SERVICE) if p.name == "net-host" else p for p in design.projects)
    assert "host project net-host must have role host" in validate_design(without(projects=wrong_role))


def test_the_perimeter_must_protect_a_known_project_with_known_levels(without, design):
    perimeter = replace(design.perimeter, projects=("ghost",), restricted_services=(), access_levels=("nobody",))
    problems = validate_design(without(perimeter=perimeter))
    assert "perimeter project ghost is not a project" in problems
    assert "perimeter uses unknown access level nobody" in problems
    assert "the perimeter restricts no service" in problems
    assert any("outside the perimeter" in p for p in problems)


def test_an_empty_perimeter_is_reported(without, design):
    assert "the perimeter protects no project" in validate_design(
        without(perimeter=replace(design.perimeter, projects=()))
    )
