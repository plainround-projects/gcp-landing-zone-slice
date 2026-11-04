# Changelog

All notable changes to this project are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Drawn architecture and flow figures in `docs/diagrams/`, light and dark, shown in the README.

### Fixed

- ARCHITECTURE.md and README now match the code where they disagreed (see the drawn figures).

## [0.1.0] - 2026-10-27

### Added

- `design/landing-zone.yaml`, `policies/org-policies.yaml` and `design/scenarios.yaml`: the slice, the four organization policies (each with a reason and the request it blocks) and the lesson's requests with their promised answers.
- Terraform: seven modules and a `lab` environment (folders, projects, organization policies, shared VPC, sensitive bucket, perimeter, test identities), dry run as the default for policies and the perimeter, native tests with a mock provider, tflint and checkov.
- `landing-zone`: check the design, explain the policies, render them for `gcloud`, simulate which control stops each request in dry-run and enforced mode. Layered, typed, tested.
- The lesson's runbook as scripts, the operating notes, ADRs and a CI workflow.
- `tech/`: 36 technology notes and an index, one file per language, tool, service and file format, for a reader new to all of them.
