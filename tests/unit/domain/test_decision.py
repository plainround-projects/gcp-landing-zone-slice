from landing_zone.domain.decision import Control, Decision, Violation


def test_a_decision_with_no_violation_is_allowed_and_names_no_control():
    decision = Decision()
    assert decision.allowed
    assert decision.stopped_by is None


def test_the_first_violation_is_the_control_that_stops_the_request():
    first = Violation(Control.IAM, "storage.objects.get", "no role")
    second = Violation(Control.ORG_POLICY, "x", "y")
    decision = Decision(violations=(first, second))
    assert not decision.allowed
    assert decision.stopped_by is first


def test_logged_only_violations_do_not_block():
    assert Decision(logged_only=(Violation(Control.VPC_SERVICE_CONTROLS, "R", "m"),)).allowed
