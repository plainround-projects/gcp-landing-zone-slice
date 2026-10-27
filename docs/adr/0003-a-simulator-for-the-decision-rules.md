# 3. A simulator of the decision rules next to the real controls

Status: accepted, 2026-10-27

## Context

The lesson's central question is "which control stopped this?": an organization policy, subnet-level IAM, the perimeter or plain IAM. The real answers need an organization and up to 30 minutes of propagation. The answers should still be reviewable in a pull request and testable in CI.

## Decision

`landing_zone.domain.landscape.Landscape` models the four controls over the design and the policies, with the perimeter in dry-run or enforced mode, and returns a `Decision` naming the control, the constraint or reason code, and the message the real service gives. `design/scenarios.yaml` lists the lesson's requests with the answer each must get. `landing-zone simulate` fails if any answer differs from the promise.

## Consequences

- A change to a policy or a subnet that breaks a promise fails `make simulate` before it reaches an organization.
- The simulator is a model, not the service: it covers the lesson's four constraints, the subnet rule and the two perimeter violation reasons, and nothing else. It never replaces the proofs in `scripts/`, which run against the real organization.
- IAM answers first in the model, as in the lesson: a principal with no read role is stopped by IAM, and the perimeter says nothing.
