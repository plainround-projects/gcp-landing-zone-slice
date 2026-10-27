import pytest

from landing_zone.domain.decision import Control, PerimeterMode
from landing_zone.domain.landscape import Landscape
from landing_zone.domain.requests import CopyObject, CreateBucket, CreateServiceAccountKey, CreateVm, ReadObject

PROD = frozenset({"group:team-prod@example-lab.org"})
DEV = frozenset({"group:team-dev@example-lab.org"})


@pytest.fixture
def enforced(design, policies):
    return Landscape(design, policies, PerimeterMode.ENFORCED)


@pytest.fixture
def dry_run(design, policies):
    return Landscape(design, policies, PerimeterMode.DRY_RUN)


def test_a_service_account_key_is_refused_by_the_organization_policy(enforced):
    stop = enforced.evaluate(CreateServiceAccountKey("dev-app")).stopped_by
    assert (stop.control, stop.detail) == (Control.ORG_POLICY, "iam.disableServiceAccountKeyCreation")
    assert "Key creation is not allowed" in stop.message


@pytest.mark.parametrize(
    ("location", "allowed"),
    [("europe-west1", True), ("EU", True), ("europe-north1", True), ("us-central1", False), ("asia-east1", False)],
)
def test_a_bucket_must_be_in_an_eu_location(enforced, location, allowed):
    decision = enforced.evaluate(CreateBucket("dev-app", location, uniform_access=True))
    assert decision.allowed is allowed
    if not allowed:
        assert "constraints/gcp.resourceLocations violated" in decision.stopped_by.message


def test_a_bucket_with_object_acls_is_refused_even_in_the_eu(enforced):
    stop = enforced.evaluate(CreateBucket("dev-app", "europe-west1", uniform_access=False)).stopped_by
    assert stop.detail == "storage.uniformBucketLevelAccess"


def test_a_vm_with_a_public_address_is_refused_and_a_private_one_is_not(enforced):
    public = enforced.evaluate(CreateVm("dev-app", "europe-west1-b", "subnet-dev", True, DEV))
    private = enforced.evaluate(CreateVm("dev-app", "europe-west1-b", "subnet-dev", False, DEV))
    assert public.stopped_by.detail == "compute.vmExternalIpAccess"
    assert private.allowed


def test_a_team_can_use_its_own_subnet_and_not_the_others(enforced):
    own = enforced.evaluate(CreateVm("prod-app", "europe-west1-b", "subnet-prod", False, PROD))
    other = enforced.evaluate(CreateVm("prod-app", "europe-west1-b", "subnet-dev", False, PROD))
    assert own.allowed
    assert (other.stopped_by.control, other.stopped_by.detail) == (Control.SHARED_VPC_IAM, "compute.subnetworks.use")
    assert "subnet-dev" in other.stopped_by.message


def test_a_vm_with_no_shared_subnet_is_only_subject_to_the_organization_policies(enforced):
    assert enforced.evaluate(CreateVm("dev-app", "europe-west1-b", None, False, frozenset())).allowed


def test_copying_data_out_of_the_perimeter_is_refused_when_enforced_though_iam_allows_it(enforced):
    stop = enforced.evaluate(CopyObject(True, "prod-data", "outside")).stopped_by
    assert (stop.control, stop.detail) == (Control.VPC_SERVICE_CONTROLS, "RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER")


def test_the_same_copy_in_dry_run_mode_succeeds_and_is_logged(dry_run):
    decision = dry_run.evaluate(CopyObject(True, "prod-data", "outside"))
    assert decision.allowed
    assert decision.logged_only[0].detail == "RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER"


def test_copying_inside_the_perimeter_or_from_outside_it_is_not_a_violation(enforced):
    assert enforced.evaluate(CopyObject(True, "prod-data", "prod-data")).allowed
    assert enforced.evaluate(CopyObject(True, "prod-app", "outside")).allowed


def test_reading_from_outside_every_access_level_is_refused_and_from_the_office_is_not(enforced):
    outside = enforced.evaluate(ReadObject(True, "prod-data", None))
    office = enforced.evaluate(ReadObject(True, "prod-data", "office"))
    other_level = enforced.evaluate(ReadObject(True, "prod-data", "not-in-the-perimeter"))
    assert outside.stopped_by.detail == "NO_MATCHING_ACCESS_LEVEL"
    assert other_level.stopped_by.detail == "NO_MATCHING_ACCESS_LEVEL"
    assert office.allowed


def test_a_read_in_a_project_outside_the_perimeter_is_not_affected_by_it(enforced):
    assert enforced.evaluate(ReadObject(True, "prod-app", None)).allowed


def test_iam_answers_first_so_a_caller_without_a_read_role_learns_nothing_about_the_perimeter(enforced):
    for request in (CopyObject(False, "prod-data", "outside"), ReadObject(False, "prod-data", None)):
        stop = enforced.evaluate(request).stopped_by
        assert (stop.control, stop.detail) == (Control.IAM, "storage.objects.get")


def test_without_the_policies_nothing_blocks_key_creation_or_regions(design):
    open_landscape = Landscape(design, (), PerimeterMode.ENFORCED)
    assert open_landscape.evaluate(CreateServiceAccountKey("dev-app")).allowed
    assert open_landscape.evaluate(CreateBucket("dev-app", "us-central1", uniform_access=False)).allowed
    assert open_landscape.evaluate(CreateVm("dev-app", "z", None, True, frozenset())).allowed


def test_a_folder_policy_binds_only_projects_in_that_folder(design, policies):
    import dataclasses

    scoped = tuple(
        dataclasses.replace(p, level="folder:production")
        if p.constraint == "iam.disableServiceAccountKeyCreation"
        else p
        for p in policies
    )
    landscape = Landscape(design, scoped, PerimeterMode.ENFORCED)
    assert not landscape.evaluate(CreateServiceAccountKey("prod-app")).allowed
    assert landscape.evaluate(CreateServiceAccountKey("dev-app")).allowed


def test_a_perimeter_that_does_not_restrict_storage_does_not_stop_a_copy(design, policies):
    import dataclasses

    only_bigquery = dataclasses.replace(design.perimeter, restricted_services=("bigquery.googleapis.com",))
    landscape = Landscape(dataclasses.replace(design, perimeter=only_bigquery), policies, PerimeterMode.ENFORCED)
    assert landscape.evaluate(CopyObject(True, "prod-data", "outside")).allowed
