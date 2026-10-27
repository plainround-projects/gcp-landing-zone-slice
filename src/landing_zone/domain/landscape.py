"""The decision rules: a design, its policies and a perimeter mode answer who would stop a request."""

from __future__ import annotations

from collections.abc import Iterable

from landing_zone.domain.decision import Control, Decision, PerimeterMode, Violation
from landing_zone.domain.design import Design, Project
from landing_zone.domain.policy import OrgPolicy
from landing_zone.domain.requests import (
    CopyObject,
    CreateBucket,
    CreateServiceAccountKey,
    CreateVm,
    ReadObject,
    Request,
)

_STORAGE = "storage.googleapis.com"
_EU_LOCATION_GROUP = "in:eu-locations"


class Landscape:
    """Evaluate requests against one design, one set of policies and one perimeter mode."""

    def __init__(self, design: Design, policies: Iterable[OrgPolicy], perimeter_mode: PerimeterMode) -> None:
        """Create the landscape; nothing is checked here, see `application.check` for the consistency rules."""
        self._design = design
        self._policies = tuple(policies)
        self._mode = perimeter_mode

    def evaluate(self, request: Request) -> Decision:
        """Decide `request`. Unknown projects are treated as outside the organization (no policy, no perimeter)."""
        match request:
            case CreateServiceAccountKey():
                return self._key(request)
            case CreateBucket():
                return self._bucket(request)
            case CreateVm():
                return self._vm(request)
            case CopyObject():
                return self._copy(request)
            case ReadObject():
                return self._read(request)

    def _policy(self, constraint: str, project: Project | None) -> OrgPolicy | None:
        for policy in self._policies:
            if policy.constraint == constraint and (project is None or policy.applies_to_folder(project.folder)):
                return policy
        return None

    def _key(self, request: CreateServiceAccountKey) -> Decision:
        policy = self._policy("iam.disableServiceAccountKeyCreation", self._design.project(request.project))
        if policy is not None and policy.enforce:
            return _refused(
                Control.ORG_POLICY,
                policy.constraint,
                "FAILED_PRECONDITION: Key creation is not allowed on this service account.",
            )
        return Decision()

    def _bucket(self, request: CreateBucket) -> Decision:
        project = self._design.project(request.project)
        locations = self._policy("gcp.resourceLocations", project)
        if locations is not None and not _location_allowed(request.location, locations.allowed_values):
            return _refused(
                Control.ORG_POLICY,
                locations.constraint,
                f"Constraint constraints/gcp.resourceLocations violated for [projects/{request.project}] "
                f"attempting to create a bucket in {request.location}.",
            )
        uniform = self._policy("storage.uniformBucketLevelAccess", project)
        if uniform is not None and uniform.enforce and not request.uniform_access:
            return _refused(
                Control.ORG_POLICY,
                uniform.constraint,
                f"Constraint constraints/storage.uniformBucketLevelAccess violated for [projects/{request.project}].",
            )
        return Decision()

    def _vm(self, request: CreateVm) -> Decision:
        project = self._design.project(request.project)
        external = self._policy("compute.vmExternalIpAccess", project)
        if request.external_ip and external is not None and external.deny_all:
            return _refused(
                Control.ORG_POLICY,
                external.constraint,
                f"Constraint constraints/compute.vmExternalIpAccess violated for project {request.project}.",
            )
        if request.subnet is not None:
            subnet = self._design.subnet(request.subnet)
            if subnet is not None and not (set(subnet.user_groups) & request.caller_groups):
                return _refused(
                    Control.SHARED_VPC_IAM,
                    "compute.subnetworks.use",
                    f"Required 'compute.subnetworks.use' permission for 'projects/{self._design.host_project}/regions/"
                    f"{self._design.region}/subnetworks/{subnet.name}'",
                )
        return Decision()

    def _copy(self, request: CopyObject) -> Decision:
        if not request.caller_can_read:
            return _refused(Control.IAM, "storage.objects.get", "the caller holds no role that allows the read")
        if self._in_perimeter(request.source_project) and not self._in_perimeter(request.destination_project):
            return self._perimeter(
                Violation(
                    Control.VPC_SERVICE_CONTROLS,
                    "RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER",
                    "Request is prohibited by organization's policy: the destination is outside the perimeter.",
                )
            )
        return Decision()

    def _read(self, request: ReadObject) -> Decision:
        if not request.caller_can_read:
            return _refused(Control.IAM, "storage.objects.get", "the caller holds no role that allows the read")
        trusted = set(self._design.perimeter.access_levels)
        if self._in_perimeter(request.project) and request.from_access_level not in trusted:
            return self._perimeter(
                Violation(
                    Control.VPC_SERVICE_CONTROLS,
                    "NO_MATCHING_ACCESS_LEVEL",
                    "Request is prohibited by organization's policy: the caller matches no access level "
                    "of the perimeter.",
                )
            )
        return Decision()

    def _in_perimeter(self, project: str) -> bool:
        perimeter = self._design.perimeter
        return project in perimeter.projects and _STORAGE in perimeter.restricted_services

    def _perimeter(self, violation: Violation) -> Decision:
        if self._mode is PerimeterMode.ENFORCED:
            return Decision(violations=(violation,))
        return Decision(logged_only=(violation,))


def _refused(control: Control, detail: str, message: str) -> Decision:
    return Decision(violations=(Violation(control, detail, message),))


def _location_allowed(location: str, allowed_values: tuple[str, ...]) -> bool:
    lowered = location.lower()
    for value in allowed_values:
        if value == _EU_LOCATION_GROUP and (lowered == "eu" or lowered.startswith("europe-")):
            return True
        if value.lower() == lowered:
            return True
    return False
