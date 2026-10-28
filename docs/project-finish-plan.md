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

**Status: Implemented; first GitHub run pending**

- Backend tests against a PostgreSQL service container.
- Frontend lint, tests, build, and `npm audit`.
- Python dependency audit with `pip-audit`.
- Secret and Docker/Compose misconfiguration scanning with Trivy.
- Docker image builds for all three application images.
- High/critical image vulnerability scanning with Trivy.

Acceptance: workflow passes on GitHub for the current `main` commit.

## Priority 3: Verify Compose operations

**Status: In progress**

- Verify start, health, logs, migrations, persistence, configuration, and clean shutdown.
- Make `make down` stop the test database too.
- Document exact lifecycle commands.

Acceptance: a clean start and stop work without orphaned containers or network errors, and data survives a non-volume shutdown.

## Priority 4: Add essential observability and rollback evidence

**Status: Pending**

- Add a minimal Prometheus + Grafana profile that scrapes the existing Order and Inventory metrics.
- Provision one practical dashboard and verify targets are up.
- Add and test a local tagged deploy/rollback script using the existing Compose images.

Acceptance: Prometheus targets are `UP`, Grafana shows live metrics, and a deploy can be rolled back to the previous image tag with health/smoke verification.

## Priority 5: Final security and portfolio pass

**Status: Pending**

- Record actual scan results and any accepted risk.
- Verify environment-variable documentation and secret handling.
- Add architecture/screenshot references and concise interview talking points.
- Update implementation status and final report.

Acceptance: docs match reality, no fabricated claims, and the repository shows working code, tests, CI, scans, operations, and observability.

## Explicit non-goals

Do not add Jenkins, Argo CD, Kubernetes, Terraform, Ansible, Razorpay, authentication, or a service mesh for this finish pass. They do not improve the essential portfolio story and would delay completion.
