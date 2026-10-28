# Project Finish Plan

Last updated: 2026-10-28

Goal: finish a credible DevOps/DevSecOps portfolio project quickly. The application already works; the remaining work is verification, CI, operational evidence, and documentation. This is not a learning roadmap.

## Priority 1: Verify the application

**Status: Complete**

- Run backend and frontend tests.
- Run the smoke test through nginx.
- Verify storefront, checkout, operations API, inventory, dashboard rendering, and metrics.
- Verify database persistence across a full `docker compose down` / `up` cycle.

Acceptance: all tests pass, smoke passes, persisted orders survive restart, and no real failures are hidden.

## Priority 2: Add GitHub Actions CI

**Status: Complete**

- Backend tests against a PostgreSQL service container.
- Frontend lint, tests, build, and `npm audit`.
- Python dependency audit with `pip-audit`.
- Secret and Docker/Compose misconfiguration scanning with Trivy.
- Docker image builds for all three application images.
- High/critical image vulnerability scanning with Trivy.

Acceptance: workflow passes on GitHub for the current `main` commit. Verified by run `40730320230` on commit `e870c0e` (all six jobs passed).

## Priority 3: Verify Compose operations

**Status: Complete**

- Verify start, health, logs, migrations, persistence, configuration, and clean shutdown.
- Make `make down` stop the test database and optional monitoring services too.
- Document exact lifecycle commands in `docs/operations.md`.

Acceptance: a clean start and stop work without orphaned containers or network errors, and data survives a non-volume shutdown.

## Priority 4: Add essential observability and rollback evidence

**Status: Complete**

- Add a minimal Prometheus + Grafana profile that scrapes the existing Order and Inventory metrics.
- Provision one practical dashboard and verify targets are up.
- Add and test a local tagged deploy/rollback script using the existing Compose images.
- Verified: both targets `UP`, Grafana/datasource healthy, 7-panel dashboard loaded, alerts inactive, `test-a`/`test-b` deploys and rollback passed smoke.

Acceptance: Prometheus targets are `UP`, Grafana shows live metrics, and a deploy can be rolled back to the previous image tag with health/smoke verification.

## Priority 5: Final security and portfolio pass

**Status: Complete**

- Record actual scan results and any accepted risk.
- Verify environment-variable documentation and secret handling.
- Add architecture/screenshot references and concise interview talking points.
- Update implementation status and final report.
- Verified: screenshots, operations runbook, security results, accepted advisory, resume bullets, and five interview scenarios are documented.

Acceptance: docs match reality, no fabricated claims, and the repository shows working code, tests, CI, scans, operations, and observability.

## Verified Evidence

- Backend: 109 tests passed.
- Frontend: 22 tests passed; lint and production build passed.
- Smoke: operations order and storefront checkout created and replayed through nginx.
- Persistence: orders and products survived a full `make down` / `up` cycle with volumes retained.
- CI: GitHub Actions run `40730320230` passed all jobs on commit `e870c0e`.
- Security: `npm audit` 0; `pip-audit` clean; Trivy image HIGH/CRITICAL 0; config 0; secrets 0.
- Observability: Prometheus targets `UP`; Grafana healthy; dashboard and datasource loaded.
- Deploy/rollback: tagged deploy and previous-tag rollback passed health and smoke checks.

## Explicit non-goals

Do not add Jenkins, Argo CD, Kubernetes, Terraform, Ansible, Razorpay, authentication, or a service mesh for this finish pass. They do not improve the essential portfolio story and would delay completion.
